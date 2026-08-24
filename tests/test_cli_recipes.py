import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock

from spacepilot.cli import cmd_recipes


def _run(**kwargs):
    args = MagicMock(**kwargs)
    out = StringIO()
    sys.stdout = out
    try:
        rc = cmd_recipes(args, {})
    finally:
        sys.stdout = sys.__stdout__
    return rc, out.getvalue()


class TestCliRecipes(unittest.TestCase):
    def test_list_reads_the_registry(self):
        rc, text = _run(recipes_action="list")
        self.assertEqual(rc, 0)
        self.assertIn("RECIPE", text)
        self.assertIn("REPO", text)
        # the shipped registry has real models, so at least one row renders
        self.assertGreater(len(text.strip().splitlines()), 1)

    def test_download_unknown_recipe_fails_cleanly(self):
        rc, text = _run(recipes_action="download", recipe_name="does-not-exist-xyz")
        self.assertEqual(rc, 1)
        self.assertIn("not found", text.lower())


if __name__ == "__main__":
    unittest.main()
