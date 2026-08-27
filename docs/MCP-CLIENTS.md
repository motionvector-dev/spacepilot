# MCP client configuration

SpacePilot's canonical local MCP client endpoint is:

```text
http://127.0.0.1:8088/mcp/v1/
```

It is a loopback-only Streamable HTTP server hosted by the stable SpacePilot
Studio process. Configure one global entry named `spacepilot` in each client.
Do not configure a second stdio entry in the same client.

Use `http://spacepilot.localhost:8088` for Studio and browser pages, including
the human documentation at `/docs`. MCP clients use the numeric loopback URL
above because some Node-based harnesses report `ENOTFOUND` for
`spacepilot.localhost`, even though both addresses reach the same local server.

## Codex

Codex CLI, the Codex IDE extension, and the ChatGPT desktop Codex integration
share the same local configuration:

```bash
codex mcp remove spacepilot
codex mcp add spacepilot --url http://127.0.0.1:8088/mcp/v1/
codex mcp get spacepilot
```

## Claude Code

```bash
claude mcp remove --scope user spacepilot
claude mcp add --transport http --scope user \
  spacepilot http://127.0.0.1:8088/mcp/v1/
claude mcp get spacepilot
```

Claude Desktop has its own configuration. Leave it empty unless the desktop
client is actually used for SpacePilot; Claude Code registration does not
require a duplicate desktop entry.

## Cursor

Use the global `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "spacepilot": {
      "url": "http://127.0.0.1:8088/mcp/v1/"
    }
  }
}
```

Preserve any unrelated servers already in the file.

## Antigravity / agy

```bash
agy mcp remove spacepilot
agy mcp add --type http \
  spacepilot http://127.0.0.1:8088/mcp/v1/
agy mcp list
```

The global config lives at `~/.gemini/config/mcp_config.json`. Preserve its
unrelated server entries. Antigravity's bundled JSON documentation still
describes remote servers as SSE even though the current CLI accepts HTTP. Probe
the connection after adding it; if that client alone cannot negotiate HTTP,
use one `spacepilot-mcp` stdio entry there as its fallback.

## OpenCode

Add this entry under the top-level `mcp` object in
`~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "spacepilot": {
      "type": "remote",
      "url": "http://127.0.0.1:8088/mcp/v1/",
      "enabled": true
    }
  }
}
```

## Pi

Pi's MCP adapter reads `~/.pi/agent/mcp.json`:

```json
{
  "mcpServers": {
    "spacepilot": {
      "type": "http",
      "url": "http://127.0.0.1:8088/mcp/v1/"
    }
  }
}
```

## Verification and restarts

First verify the managed server itself:

```bash
curl --fail http://127.0.0.1:8088/healthz
```

Then use each client's MCP list or inspect command. Existing sessions may cache
their tool inventory; start a new session after changing a registration. A
client that cannot negotiate Streamable HTTP may use the `spacepilot-mcp` stdio
entry point instead, but it must still have only one SpacePilot entry.
