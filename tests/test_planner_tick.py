import json
import os
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from orchestrator import planner_tick


class TestPlannerTick(unittest.TestCase):
    def test_call_planner_prefers_codex_last_message_file(self):
        payload = {
            "title": "威力彩 OOS 驗證",
            "slug": "power-oos-validation",
            "prompt_markdown": "## Objective\nA\n## Scope\nB\n## Constraints\nC\n## Acceptance Criteria\nD\n## Handoff Notes\nE",
        }

        def fake_run(command, capture_output, text, timeout):
            self.assertEqual(command[-1], "prompt")
            self.assertEqual(command[-3], "--output-last-message")
            output_path = command[command.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            return subprocess.CompletedProcess(command, 0, stdout="OpenAI Codex banner", stderr="")

        with patch("orchestrator.planner_tick.common.planner_command", return_value=("codex", ["/opt/homebrew/bin/codex", "exec", "prompt"])), \
             patch("orchestrator.planner_tick.subprocess.run", side_effect=fake_run):
            runtime, raw = planner_tick._call_planner("prompt", "codex")

        self.assertEqual(runtime, "codex")
        self.assertEqual(json.loads(raw), payload)

    def test_call_planner_falls_back_to_stdout_when_last_message_missing(self):
        stdout_payload = '{"title":"任務","slug":"task-slug","prompt_markdown":"## Objective\\nA\\n## Scope\\nB\\n## Constraints\\nC\\n## Acceptance Criteria\\nD\\n## Handoff Notes\\nE"}'

        with patch("orchestrator.planner_tick.common.planner_command", return_value=("claude", ["/bin/claude", "-p", "prompt"])), \
             patch(
                 "orchestrator.planner_tick.subprocess.run",
                 return_value=subprocess.CompletedProcess(["/bin/claude"], 0, stdout=stdout_payload, stderr=""),
             ):
            runtime, raw = planner_tick._call_planner("prompt", "claude")

        self.assertEqual(runtime, "claude")
        self.assertEqual(raw, stdout_payload)

    def test_generate_planner_payload_falls_back_to_alternate_provider(self):
        valid_payload = {
            "title": "威力彩 WQ 驗證",
            "slug": "power-wq-validation",
            "prompt_markdown": "## Objective\nA\n## Scope\nB\n## Constraints\nC\n## Acceptance Criteria\nD\n## Handoff Notes\nE",
        }

        with patch("orchestrator.planner_tick.common.provider_available", return_value=(True, "Ready")), \
             patch(
                 "orchestrator.planner_tick._attempt_planner_payload",
                 side_effect=[
                     (None, "codex", "ERROR: You've hit your usage limit", "failed to parse planner JSON output"),
                     (valid_payload, "claude", json.dumps(valid_payload, ensure_ascii=False), ""),
                 ],
             ):
            payload, planner_source, effective_provider, requested_provider, error = planner_tick._generate_planner_payload(
                "prompt",
                "codex",
            )

        self.assertEqual(payload, valid_payload)
        self.assertEqual(planner_source, "claude")
        self.assertEqual(effective_provider, "claude")
        self.assertEqual(requested_provider, "codex")
        self.assertEqual(error, "")

    def test_runtime_blocker_skips_local_fallback_task_creation(self):
        with patch("orchestrator.planner_tick.common.ensure_dirs"), \
             patch("orchestrator.planner_tick.db.get_planner_provider", return_value="codex"), \
             patch("orchestrator.planner_tick.db.is_scheduler_enabled", return_value=True), \
             patch("orchestrator.planner_tick.db.get_latest_task", return_value=None), \
             patch("orchestrator.planner_tick._build_meta_prompt", return_value=("backlog", [], "prompt")), \
             patch(
                 "orchestrator.planner_tick._generate_planner_payload",
                 return_value=(None, "fallback", "codex", "codex", "codex: usage limit | claude: hit your limit"),
             ), \
             patch("orchestrator.planner_tick.db.create_task") as create_task_mock, \
             patch("orchestrator.planner_tick.db.log_tick"), \
             patch("orchestrator.planner_tick.common.log_jsonl"):
            planner_tick.run(force=True)

        create_task_mock.assert_not_called()

    def test_stale_blocked_env_rate_limit_is_auto_resolved(self):
        stale_task = {
            "id": 86,
            "status": "BLOCKED_ENV",
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            "completed_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            "error_message": "You've hit your rate limit. Please wait for your limit to reset.",
            "completed_text": "docs.github.com/en/copilot/concepts/rate-limits\nRequests 0 Premium",
        }

        with patch("orchestrator.planner_tick.db.update_task") as update_task_mock, \
             patch("orchestrator.planner_tick.db.log_tick"), \
             patch("orchestrator.planner_tick.common.log_jsonl"):
            should_block, message = planner_tick._resolve_previous_task_blocker(stale_task)

        self.assertFalse(should_block)
        self.assertIsNone(message)
        update_task_mock.assert_called_once()
        self.assertEqual(update_task_mock.call_args.kwargs["status"], "FAILED_RATE_LIMIT")

    def test_monitoring_duplicate_source_is_suppressed(self):
        signal_state = {"state": "SIGNAL_SATURATED", "confidence_score": 0.8}
        inflight = {
            "id": 287,
            "status": "QUEUED",
            "dedupe_key": "monitoring:deep_research_cold:2026-04-28",
        }
        with patch(
            "orchestrator.planner_tick.db.get_inflight_auto_monitor_by_source_task_type",
            return_value=inflight,
        ), patch(
            "orchestrator.planner_tick.db.get_inflight_task_by_dedupe_key",
            return_value=None,
        ), patch(
            "orchestrator.planner_tick.db.get_recent_completed_task_by_dedupe_key",
            return_value=None,
        ):
            should_skip, reason = planner_tick._check_task_dedupe(
                "monitoring:deep_research_cold:2026-04-28",
                signal_state,
                monitor_source_task_type="deep_research_cold",
            )

        self.assertTrue(should_skip)
        self.assertIn("DUPLICATE_MONITORING_SOURCE:", reason)
        self.assertIn("source=deep_research_cold", reason)

    def test_duplicate_cleanup_statuses_are_terminal(self):
        self.assertIn("CANCELLED_DUPLICATE", planner_tick.TERMINAL_TASK_STATUSES)
        self.assertIn("SKIPPED_DUPLICATE", planner_tick.TERMINAL_TASK_STATUSES)


if __name__ == "__main__":
    unittest.main()
