#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recap — Session Start Hook

Restores context from previous sessions when a new Claude Code session begins.
Outputs JSON with hookSpecificOutput.additionalContext for Claude Code injection.
"""

import warnings

warnings.filterwarnings("ignore")

import json
import os
import sys
from io import StringIO
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io as _io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "detach"):
        sys.stdout = _io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# Add scripts/ to path for recap_core import
HOOK_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOK_DIR.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from recap_core import (
    get_config,
    get_git_context,
    get_recent_sessions,
    format_restore_context,
)


def should_skip() -> bool:
    """Skip injection in non-interactive mode."""
    return os.environ.get("CLAUDE_NON_INTERACTIVE") == "1"


def main() -> None:
    if should_skip():
        sys.exit(0)

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

    # Allow projects to opt out of recap (e.g., the recap dev project itself)
    if (project_dir / ".claude" / "recap" / ".skip").exists():
        print(json.dumps({}), flush=True)
        return

    recap_dir = project_dir / ".claude" / "recap"

    # If recap hasn't been used yet, output a brief intro
    if not recap_dir.is_dir():
        result = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "<recap>\n"
                    "Recap is installed but no sessions have been saved yet.\n"
                    "Use `/recap save` at the end of your session to capture your work.\n"
                    "</recap>"
                ),
            }
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return

    # Gather context
    config = get_config(recap_dir)
    restore_count = config.get("restore_count", 3)

    git_context = get_git_context(project_dir)
    recent_sessions = get_recent_sessions(recap_dir, count=restore_count)
    restore_text = format_restore_context(recent_sessions, git_context)

    output = StringIO()
    output.write("<recap>\n")
    output.write("Session context restored by Recap. Review previous work below.\n\n")
    output.write(restore_text)
    output.write("\n</recap>")

    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": output.getvalue(),
        }
    }

    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
