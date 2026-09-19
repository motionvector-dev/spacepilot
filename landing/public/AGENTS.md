# AGENTS.md — SpacePilot Autonomous Agent Grounding

## What SpacePilot Is

SpacePilot is a provenance-first decision layer for single-owner AI compute fleets.
It dynamically schedules generative workloads across heterogeneous hardware based on real, empirical readiness rather than rated hardware specifications.

## Global Installation

```bash
uv tool install spacepilot
```

## CLI Subcommands

- `spacepilot probe`: Inspects local silicon, memory limits, and backend.
- `spacepilot doctor`: Validates local ffmpeg, model weights, and cloud credentials.
- `spacepilot models list`: Evaluates all 40 models against local hardware fit.
- `spacepilot runtimes list`: Lists available inference runtimes.
- `spacepilot-mcp`: Stdio Model Context Protocol (MCP) server for agent tools.

## FastMCP Server Integration

Add to agent configuration:

```json
{
  "mcpServers": {
    "spacepilot": {
      "command": "spacepilot-mcp"
    }
  }
}
```

## Public Resources

- PyPI Package: https://pypi.org/project/spacepilot/
- GitHub: https://github.com/motionvector-dev/spacepilot
- Web Documentation: https://spacepilot.dev/docs
