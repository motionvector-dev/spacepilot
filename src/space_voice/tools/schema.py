TOOLS_SCHEMA = [
    {
        "name": "git_status",
        "description": "Get the current git status of the repository.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "git_diff",
        "description": "Get the git diff for uncommitted changes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "run_spacepilot_cli",
        "description": "Run the spacepilot CLI with a given command.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "The command or arguments to pass to spacepilot."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a local file.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {
                    "type": "STRING",
                    "description": "The relative or absolute path of the file to read."
                }
            },
            "required": ["path"]
        }
    }
]
