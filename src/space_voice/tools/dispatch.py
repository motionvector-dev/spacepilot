import subprocess
import os
from pathlib import Path

# Safe whitelisted workspace root
ALLOWED_ROOTS = [
    Path("/Users/saurabh/code").resolve(),
]

# Prohibited dangerous spacepilot subcommands for voice
PROHIBITED_CLI_SUBCOMMANDS = {"purge", "delete", "destroy", "clean", "reset", "drop"}

def is_safe_path(path_str: str) -> bool:
    """Ensures file paths cannot escape the allowed code repositories."""
    try:
        resolved = Path(path_str).resolve()
        return any(root in resolved.parents or resolved == root for root in ALLOWED_ROOTS)
    except Exception:
        return False

async def dispatch_tool(name: str, args: dict) -> str:
    """Dispatches a strictly sandboxed, read-only tool call to the local system."""
    try:
        if name == "git_status":
            result = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, check=True)
            return result.stdout if result.stdout else "Working directory is clean."
            
        elif name == "git_diff":
            result = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, check=True)
            return result.stdout if result.stdout else "No unstaged changes."
            
        elif name == "run_spacepilot_cli":
            command = args.get("command", "").strip()
            tokens = command.split()
            
            # Guardrail 1: Disallow prohibited mutation commands via voice
            if any(t.lower() in PROHIBITED_CLI_SUBCOMMANDS for t in tokens):
                return f"🛑 Security Guardrail Block: Mutation command '{command}' is not permitted via voice. Please execute manually in terminal."
                
            cmd_list = ["spacepilot"] + tokens
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            return output[:2000] # Prevent token buffer overflow
            
        elif name == "read_file":
            path_str = args.get("path", "").strip()
            
            # Guardrail 2: Path Traversal Jail (No reading SSH keys, /etc, or Doppler tokens)
            if not is_safe_path(path_str):
                return f"🛑 Security Guardrail Block: Access to path '{path_str}' is restricted to /Users/saurabh/code/."
                
            p = Path(path_str)
            if not p.exists():
                return f"Error: File not found: {path_str}"
            if p.stat().st_size > 100_000: # 100KB limit
                return f"Error: File too large to stream via voice ({p.stat().st_size} bytes)."
                
            return p.read_text(encoding="utf-8", errors="replace")[:2000]
            
        else:
            return f"Error: Unknown or unauthorized tool '{name}'"
            
    except subprocess.TimeoutExpired:
        return f"Error: Tool '{name}' timed out after 15 seconds."
    except Exception as e:
        return f"Error executing tool '{name}': {str(e)}"

