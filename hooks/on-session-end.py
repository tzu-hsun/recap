#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recap — Session End Hook

Captures final git state when a Claude Code session ends.
Outputs a prompt asking Claude to summarize the session before exit.

Note: Claude Code's Stop hook may have limitations on what can be captured.
If auto-capture is insufficient, use `/recap save` for manual capture.
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io as _io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "detach"):
        sys.stdout = _io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# Add scripts/ to path
HOOK_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOK_DIR.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from recap_core import get_git_context


def should_skip() -> bool:
    return os.environ.get("CLAUDE_NON_INTERACTIVE") == "1"


def main() -> None:
    if should_skip():
        sys.exit(0)

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    git_context = get_git_context(project_dir)

    # Build a summary of final state for the stop event
    state_lines = []
    if git_context.get("is_git"):
        state_lines.append(f"Branch: {git_context.get('branch', 'unknown')}")
        if git_context.get("status_clean"):
            state_lines.append("Working directory: Clean")
        else:
            state_lines.append(
                f"Uncommitted changes: {git_context.get('uncommitted_count', 0)} file(s)"
            )
            for f in git_context.get("changed_files", [])[:10]:
                state_lines.append(f"  - {f}")

    # Stop hooks don't support hookSpecificOutput.additionalContext.
    # Just exit cleanly — session-start hook handles reminders.
    _ = state_lines  # computed for future use if Stop hooks gain context support


if __name__ == "__main__":
    main()
