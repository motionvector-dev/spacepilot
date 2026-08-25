"""Every CLI handler returns a real exit status.

Handlers used to return None on success and failure alike; main() discarded
the value, so every verb exited 0 — including ones that had just printed a
refusal. main() now propagates the handler's return, and this guard keeps any
new handler from quietly reverting to the old shape.
"""

import ast
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "spacepilot" / "cli.py"


def _handlers():
    tree = ast.parse(CLI.read_text())
    found = [n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name.startswith("cmd_")]
    assert len(found) >= 20, "handler walk is vacuous"
    return found


def test_every_handler_is_annotated_int():
    bad = [n.name for n in _handlers() if getattr(n.returns, "id", None) != "int"]
    assert not bad, f"handlers without an int return annotation: {bad}"


def test_no_handler_has_a_bare_return():
    """A bare `return` is an exit status nobody chose."""
    bad = []
    for fn in _handlers():
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Return) and sub.value is None:
                bad.append(f"{fn.name}:{sub.lineno}")
    assert not bad, f"bare returns: {bad}"
