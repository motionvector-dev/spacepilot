import subprocess
import os

async def dispatch_tool(name: str, args: dict) -> str:
    """Dispatches a tool call to the corresponding local function."""
    try:
        if name == "git_status":
            result = subprocess.run(["git", "status"], capture_output=True, text=True, check=True)
            return result.stdout
        elif name == "git_diff":
            result = subprocess.run(["git", "diff"], capture_output=True, text=True, check=True)
            return result.stdout if result.stdout else "No unstaged changes."
        elif name == "run_spacepilot_cli":
            command = args.get("command", "")
            cmd_list = ["spacepilot"] + command.split()
            result = subprocess.run(cmd_list, capture_output=True, text=True)
            return result.stdout + result.stderr
        elif name == "read_file":
            path = args.get("path", "")
            if not os.path.exists(path):
                return f"Error: File not found: {path}"
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"Error: Unknown tool {name}"
    except Exception as e:
        return f"Error executing tool {name}: {str(e)}"
