from __future__ import annotations

import unittest

from wbc_backend.ux.mode_launcher import build_mode_command


class TestModeLauncher(unittest.TestCase):
    def test_build_mode_command_for_wbc(self):
        command = build_mode_command("wbc", extra_args=["--game", "C01"])
        self.assertTrue(command[0].endswith("python") or command[0].endswith("python3"))
        self.assertTrue(command[1].endswith("main.py"))
        self.assertEqual(command[-2:], ["--game", "C01"])

    def test_build_mode_command_for_mlb(self):
        command = build_mode_command("mlb-benchmark")
        self.assertTrue(command[1].endswith("scripts/run_mlb_decision_quality.py"))

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            build_mode_command("unknown")


if __name__ == "__main__":
    unittest.main()
