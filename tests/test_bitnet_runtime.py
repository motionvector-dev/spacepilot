"""BitNet/Ternary Bonsai runtime registration: bitnet-cpp and
llama-cpp-prism recipes, their wiring into the model manifests' notes, and
fly.py plan's visibility into the BitNet GGUF entry.

Neither recipe's binary is built on this machine (both are CMake builds of
a llama.cpp fork, recorded not run -- see each recipe's own notes), so the
fly.py plan assertions here check that the entry is *flyable in principle*
(a runtime is registered and wired) while still reporting BLOCKED with a
concrete install fix, not that the binary is actually present.
"""

import re as _re
from pathlib import Path

import pytest
import yaml

from spacepilot.runtimes import load_runtimes, parse_runtime

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "spacepilot" / "registry" / "runtimes"
MODEL_DIR = ROOT / "spacepilot" / "registry" / "models"
TOOLS_DIR = ROOT / "tools"


# ------------------------------------------------------------- recipe parsing

def test_bitnet_cpp_recipe_parses():
    raw = yaml.safe_load((RUNTIME_DIR / "bitnet-cpp.yaml").read_text())
    r = parse_runtime(raw, "bitnet-cpp.yaml")
    assert r.id == "bitnet-cpp"
    assert r.install.method == "script"
    assert r.install.script_url.startswith("https://")
    assert r.verify_binary == "bitnet-cli"
    assert r.verify_import is None
    assert r.backends == ["cpu"]
    assert r.runs == ["bitnet-b1-58-2b4t"]


def test_llama_cpp_prism_recipe_parses():
    raw = yaml.safe_load((RUNTIME_DIR / "llama-cpp-prism.yaml").read_text())
    r = parse_runtime(raw, "llama-cpp-prism.yaml")
    assert r.id == "llama-cpp-prism"
    assert r.install.method == "script"
    assert r.install.script_url.startswith("https://")
    assert r.verify_binary == "llama-cli-prism"
    assert set(r.backends) == {"cpu", "metal"}
    assert r.runs == ["ternary-bonsai-8b"]


def test_both_recipes_are_in_the_shipped_runtime_registry():
    """load_runtimes() walks spacepilot/registry/runtimes/*.yaml -- both new
    files must actually be picked up, not just individually parseable."""
    rs = load_runtimes()
    assert "bitnet-cpp" in rs
    assert "llama-cpp-prism" in rs


def test_recipes_pin_real_commits_not_moving_refs():
    """These are CMake source-tree builds with no upstream release script --
    the whole point of registering them is a real, checkable commit pin."""
    for name, needle in (
        ("bitnet-cpp.yaml", "0b341e582afbf9e1011f24744b554c96a3477eb5"),
        ("llama-cpp-prism.yaml", "d8f26eec76da6d09bb708bcba51ef64b8cd868a3"),
    ):
        text = (RUNTIME_DIR / name).read_text()
        assert needle in text, f"{name} does not name its pinned commit"


# ------------------------------------------------------------- manifest wiring

def test_bitnet_manifest_no_longer_says_recipe_pending():
    text = (MODEL_DIR / "bitnet-b1-58-2b4t.yaml").read_text()
    assert "recipe pending" not in text
    assert "registry/runtimes/bitnet-cpp.yaml" in text


def test_bonsai_manifest_no_longer_says_recipe_pending():
    text = (MODEL_DIR / "ternary-bonsai-8b.yaml").read_text()
    assert "recipe pending" not in text
    assert "registry/runtimes/llama-cpp-prism.yaml" in text


def test_every_runs_entry_still_names_a_registered_model():
    """The pre-existing cross-check (tests/test_runtimes_registry.py) proves
    this globally; this is the narrow version naming exactly the two new
    entries, so a future rename of either model manifest fails loudly here
    too."""
    from spacepilot.model_registry import registry

    model_ids = set(registry().models.keys())
    assert "bitnet-b1-58-2b4t" in model_ids
    assert "ternary-bonsai-8b" in model_ids


# --------------------------------------------------------------------- fly.py

def test_fly_plan_shows_the_bitnet_gguf_entry():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import fly

    rows = fly.plan_rows()
    row = next((r for r in rows if r.variant.id == "bitnet-b1-58-2b4t-gguf-i2s"), None)
    assert row is not None, "bitnet-b1-58-2b4t-gguf-i2s missing from fly.py plan"
    assert row.plan is not None
    assert row.plan.runtime_id == "bitnet-cpp"
    assert row.plan.cli == "text"
    assert "bitnet-b1-58-2b4t-gguf-i2s" in row.command


def test_fly_plan_reports_exactly_which_install_bitnet_needs():
    """The binary is not built on this machine, so the entry must stay
    BLOCKED -- but with a concrete, actionable install command, not a bare
    refusal (fly.py's own contract for a registered-but-uninstalled
    runtime, see runtime_status())."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import fly

    rows = fly.plan_rows()
    row = next(r for r in rows if r.variant.id == "bitnet-b1-58-2b4t-gguf-i2s")
    if row.runtime.installed:
        pytest.skip("bitnet-cli happens to be built and on PATH on this machine")
    assert row.runtime.install_cmd == "spacepilot runtimes install bitnet-cpp"
    assert row.runtime.reason


# -------------------------------------------------- install argument wiring

def test_install_scripts_needing_a_positional_arg_declare_a_template_placeholder():
    """`tools/install-bitnet-cpp.sh` refuses to run without its GGUF
    directory as `$1` (`GGUF_DIR="${1:?usage: ...}"`) -- since #142 that
    guard fails fast with a clear message instead of failing deep inside a
    CMake build. But the guard only helps if something upstream actually
    supplies `$1`. `spacepilot.runtimes.install_command()` builds
    `curl -fsSL <script_url> | sh` with nothing after `sh` unless the
    runtime's own recipe says an argument is needed and how to fill it in --
    so every install script under tools/ that requires a positional
    argument must have a matching template placeholder (e.g. `{model_dir}`)
    in its runtime recipe's `install.args`, or that argument silently never
    arrives.
    """
    positional_arg_re = _re.compile(r"\$\{1:\?")
    checked_any = False
    for runtime_path in sorted(RUNTIME_DIR.glob("*.yaml")):
        raw = yaml.safe_load(runtime_path.read_text())
        install = raw.get("install", {})
        if install.get("method") != "script":
            continue
        script_url = install.get("script_url", "")
        script_name = script_url.rsplit("/", 1)[-1]
        script_path = TOOLS_DIR / script_name
        if not script_path.is_file():
            # Not one of ours (e.g. desert-ant's upstream install.sh) --
            # nothing here to check against.
            continue
        checked_any = True
        text = script_path.read_text()
        if not positional_arg_re.search(text):
            continue
        args = install.get("args") or []
        assert any("{" in a and "}" in a for a in args), (
            f"{runtime_path.name}: {script_name} requires a positional "
            f"argument ({positional_arg_re.pattern}) but install.args "
            f"({args!r}) has no template placeholder for it"
        )
    assert checked_any, "expected at least one runtime recipe pointing at a tools/ install script"


def test_bitnet_cpp_yaml_declares_the_model_dir_placeholder():
    raw = yaml.safe_load((RUNTIME_DIR / "bitnet-cpp.yaml").read_text())
    args = raw.get("install", {}).get("args") or []
    assert "{model_dir}" in args, (
        "bitnet-cpp.yaml's install.args must carry a {model_dir} placeholder -- "
        "tools/install-bitnet-cpp.sh's $1 is the fetched GGUF directory"
    )


def test_llama_cpp_prism_yaml_has_no_spurious_model_dir_placeholder():
    """llama-cpp-prism's install script takes no positional argument at
    all -- unlike bitnet-cpp it never reads a GGUF path itself (Ternary
    Bonsai's checkpoint is only ever named later, on the `spacepilot run`
    command line), so it must not carry the same template."""
    raw = yaml.safe_load((RUNTIME_DIR / "llama-cpp-prism.yaml").read_text())
    args = raw.get("install", {}).get("args") or []
    assert args == []
