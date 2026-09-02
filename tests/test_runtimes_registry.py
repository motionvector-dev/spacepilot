"""Cross-checks between the runtime registry and the model registry."""

def test_every_runs_entry_names_a_registered_model():
    """A runtime's runs[] is a capability claim; it must point at a model file
    that exists. mlx-audio claimed musicgen and bark, stable-audio-tools
    claimed stable-audio-open — none was a model id, and nothing noticed."""
    from spacepilot.model_registry import registry
    from spacepilot.runtimes import load_runtimes

    model_ids = set(registry().models.keys())
    assert len(model_ids) > 10, "model registry walk is vacuous"
    runtimes = load_runtimes()
    assert len(runtimes) >= 9, "runtime walk is vacuous"
    dangling = {
        (rt.id, m) for rt in runtimes.values() for m in rt.runs
        if m not in model_ids
    }
    assert not dangling, f"runs[] entries pointing at no model: {sorted(dangling)}"
