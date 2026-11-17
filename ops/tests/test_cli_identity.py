import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import amber_sync as sync
import site_builder


class CliIdentityTests(unittest.TestCase):
    def test_script_uses_canonical_error_and_executes_command_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({"root": str(root)}))
            output = io.StringIO()
            with patch.object(sync, "locked", return_value=contextlib.nullcontext()), \
                 patch.object(sync, "Engine") as engine, \
                 patch.object(sys, "argv", ["amber_sync.py", "--config", str(config), "run"]), \
                 contextlib.redirect_stdout(output):
                engine.return_value.run.side_effect = site_builder.SyncError("WEBSITE_MAIN_REWIND_OR_DIVERGENCE")
                with self.assertRaises(SystemExit) as exit_result:
                    runpy.run_path(str(Path(sync.__file__)), run_name="__main__")
                self.assertEqual(exit_result.exception.code, 1)
                engine.assert_called_once()
                engine.return_value.run.assert_called_once_with()
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event"], "fatal")
            self.assertEqual(events[0]["code"], "WEBSITE_MAIN_REWIND_OR_DIVERGENCE")
