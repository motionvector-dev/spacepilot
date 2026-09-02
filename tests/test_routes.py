"""Route derivation: which registry variant a wired runtime actually serves.

`spacepilot.routes` is the one place `_route_for`, the text and embedding
execution services, and the CLI all read to answer "is this variant served,
and by what". These tests pin the derivation rule itself, independent of any
one caller.
"""

from spacepilot.routes import default_variant_id, route_for, served_variants


def test_a_variant_not_in_the_runtimes_runs_list_is_not_served():
    # deepseek-r1-distill-qwen-7b is metal-capable and even sits in
    # llama-cpp's `runs:`, but llama-cpp has no wired driver — see
    # WIRED_RUNTIMES in spacepilot/routes.py.
    assert route_for("deepseek-r1-distill-qwen-7b") is None


def test_a_variant_in_a_wired_runtimes_runs_list_with_the_right_backend_is_served():
    assert route_for("qwen1-5-moe-a2-7b-chat-4bit") == "mlx-lm"
    assert route_for("qwen3-8-27b-4bit") == "mlx-lm"


def test_the_embedding_variant_is_still_served():
    assert route_for("qwen3-embedding-0-6b-8bit") == "mlx-lm"


def test_an_unknown_variant_id_is_not_served():
    assert route_for("not-a-real-variant") is None


def test_a_variant_absent_from_the_local_backend_is_not_served():
    assert route_for("qwen3-8-27b-4bit", backend="cuda") is None


def test_served_variants_lists_every_mlx_lm_text_variant_in_runs_order():
    ids = [v.id for v in served_variants("text")]
    assert ids == ["qwen3-8-27b-4bit", "qwen1-5-moe-a2-7b-chat-4bit"]


def test_served_variants_for_embedding_is_the_one_embedding_variant():
    ids = [v.id for v in served_variants("embedding")]
    assert ids == ["qwen3-embedding-0-6b-8bit"]


def test_served_variants_excludes_unwired_kinds():
    # vision has a registry entry (qwen2-5-vl) but no wired runtime.
    assert served_variants("vision") == []


def test_default_variant_id_is_the_first_served_one():
    assert default_variant_id("text") == "qwen3-8-27b-4bit"
    assert default_variant_id("embedding") == "qwen3-embedding-0-6b-8bit"


def test_default_variant_id_is_none_when_nothing_is_served():
    assert default_variant_id("vision") is None
