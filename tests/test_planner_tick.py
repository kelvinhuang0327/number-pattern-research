import json
import os
import subprocess
import unittest
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


if __name__ == "__main__":
    unittest.main()
