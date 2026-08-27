# Local setup and upgrades

This is the canonical operator guide for installing SpacePilot on a developer
machine, selecting inference interpreters, and exposing its MCP server to local
agent clients.

## The single-install rule

Keep exactly one SpacePilot control-plane installation:

- `spacepilot` is installed with pipx and is the only supported command.
- ML runtimes do not belong in the pipx environment. They run through the
  interpreter selected by `SPACEPILOT_PYTHON` or `.spacepilot_config.json`.
- mflux deliberately uses its own interpreter through `SPACEPILOT_MFLUX_BIN` or
  `mflux_bin_dir`.

The separate runtime interpreters are transitional. The intended replacement
is the immutable runtime-capsule design tracked in
[issue #80](https://github.com/motionvector-dev/spacepilot/issues/80) and
`docs/design/RUNTIME-CAPSULES.md`.

## Install or replace the CLI

Run this from a clean, current checkout:

```bash
git status --short
git pull --ff-only
pipx install --force .
```

`--force` replaces the existing `spacepilot` pipx environment in place. Do not
also run `pip install -e .`, install a second pipx suffix, or copy launchers into
another bin directory.

Verify the result from outside the repository so the checkout cannot shadow
the installed package:

```bash
cd /tmp
command -v spacepilot
type -a spacepilot
spacepilot run --help
```

There should be one `spacepilot` path. Until the CLI exposes build provenance
through `spacepilot --version`, verify a newly added command explicitly—for
example, `spacepilot run text --help`.

## Configure runtime interpreters

The repository carries no `.venv`. On the primary development machine, bare
`python3` resolves to base Conda and is not the SpacePilot project interpreter.

When running from a checkout, the gitignored, machine-local
`.spacepilot_config.json` can select the runtime interpreter:

```json
{
  "python_bin": "/absolute/path/to/the/project/python",
  "mflux_bin_dir": "/absolute/path/to/the/mflux/environment/bin"
}
```

The current packaged CLI does not discover that checkout-local file when it is
run from pipx. Until configuration moves to a stable user-data path, set the
environment variable for installed CLI invocations. Environment variables also
override the checkout file:

```bash
SPACEPILOT_PYTHON=/absolute/path/to/python spacepilot runtimes check mlx-lm
SPACEPILOT_MFLUX_BIN=/absolute/path/to/mflux/bin spacepilot runtimes check mflux
```

Never put tokens or API keys in this file. Secrets remain under Doppler as
described in `AGENTS.md`.

## Prepare and run the Qwen text route

Inspect before installing or downloading anything:

```bash
spacepilot runtimes check mlx-lm
spacepilot recipes list
```

Then prepare the runtime and exact pinned model snapshot:

```bash
spacepilot runtimes install mlx-lm
spacepilot recipes download qwen3-8-27b-4bit
```

Plan interactively before approving the large allocation:

```bash
spacepilot run text --prompt "Explain this repository in five bullets"
```

For a non-interactive caller, `--yes` is mandatory. The safe route currently
bounds output to 256 tokens and the KV cache to 4096 tokens:

```bash
spacepilot run text \
  --prompt "Explain this repository in five bullets" \
  --max-tokens 256 \
  --max-kv-size 4096 \
  --yes
```

## Register the MCP server

The MCP server is an entry point inside the one pipx environment; do not make a
second Python environment for it. The `spacepilot-mcp` command is installed
beside `spacepilot`.

Codex, the ChatGPT desktop app, and the Codex IDE extension share the same local
Codex MCP configuration, so register SpacePilot only once for that group:

```bash
codex mcp add spacepilot \
  --env SPACEPILOT_PYTHON=/absolute/path/to/the/project/python \
  -- spacepilot-mcp
codex mcp get spacepilot
```

Claude Code has separate configuration and therefore needs its own registration:

```bash
claude mcp add --scope user spacepilot \
  -e SPACEPILOT_PYTHON=/absolute/path/to/the/project/python \
  -- spacepilot-mcp
claude mcp get spacepilot
```

Register Cursor only if it is actively used; its configuration is independent.
One registration in each client is expected and does not create another
SpacePilot installation. Each client starts the same pipx-hosted stdio server
when needed.

After changing an MCP registration, start a new client session if the current
session does not refresh its tool inventory.

## Audit and repair

```bash
type -a spacepilot
pipx list
codex mcp list
claude mcp list
spacepilot runtimes list
```

Expected shape:

- one pipx environment named `spacepilot`;
- one `spacepilot` PATH entry;
- at most one MCP entry named `spacepilot` per client;
- ML runtime packages only in their configured runtime interpreters.

If an old MCP entry points into a deleted worktree or a different Python
environment, remove that client entry before adding the canonical one:

```bash
codex mcp remove spacepilot
claude mcp remove --scope user spacepilot
```

Removal only changes that client's registration. It does not uninstall the
pipx package or delete model weights.
