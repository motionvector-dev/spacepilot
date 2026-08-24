import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock

from spacepilot.cli import cmd_lora


def _run(**kwargs):
    out = StringIO()
    sys.stdout = out
    try:
        rc = cmd_lora(MagicMock(**kwargs), {})
    finally:
        sys.stdout = sys.__stdout__
    return rc, out.getvalue()


class TestCliLora(unittest.TestCase):
    def test_list_still_works(self):
        """Gating training must not take the honest read down with it.

        The API and MCP surfaces both keep `list` working; the CLI must agree.
        """
        rc, text = _run(lora_action="list")
        self.assertEqual(rc, 0)
        self.assertNotIn("Traceback", text)

    def test_train_is_gated_cleanly(self):
        """Training was a simulation. It must refuse — as a message, not a crash."""
        rc, text = _run(lora_action="train")
        self.assertEqual(rc, 1)
        self.assertIn("not implemented", text.lower())
        self.assertIn("simulated", text.lower())


if __name__ == "__main__":
    unittest.main()
