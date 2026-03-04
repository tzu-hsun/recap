#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recap Core — Session memory for Claude Code.

Zero-dependency (stdlib only) module providing:
  - Git context gathering
  - Journal management (append, rotate, read)
  - Session formatting (save and restore)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io as _io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "detach"):
        sys.stdout = _io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MAX_JOURNAL_LINES = 2000
JOURNAL_PREFIX = "journal-"
RECAP_DIR_NAME = "recap"
DEFAULT_RESTORE_COUNT = 3


# =============================================================================
# Path Utilities
# =============================================================================


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start to find a directory containing .git or .claude/.

    Falls back to start (or cwd) if neither is found.
    """
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / ".claude").exists():
            return parent
    return current


def get_recap_dir(project_root: Path | None = None) -> Path:
    """Return .claude/recap/ inside the project, creating it if needed."""
    root = project_root or find_project_root()
    recap_dir = root / ".claude" / RECAP_DIR_NAME
    recap_dir.mkdir(parents=True, exist_ok=True)
    return recap_dir


# =============================================================================
# Git Utilities
# =============================================================================


def _run_git(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a git command, forcing UTF-8 output."""
    try:
        result = subprocess.run(
            ["git", "-c", "i18n.logOutputEncoding=UTF-8"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def is_git_repo(project_root: Path) -> bool:
    """Check if project_root is inside a git repository."""
    rc, _, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=project_root)
    return rc == 0


def get_git_context(project_root: Path | None = None) -> dict:
    """Gather git state: branch, status, recent commits, modified files.

    Returns an empty-ish dict gracefully if not a git repo.
    """
    root = project_root or find_project_root()

    if not is_git_repo(root):
        return {
            "is_git": False,
            "branch": None,
            "status_clean": True,
            "uncommitted_count": 0,
            "changed_files": [],
            "recent_commits": [],
        }

    # Branch
    _, branch_out, _ = _run_git(["branch", "--show-current"], cwd=root)
    branch = branch_out.strip() or "HEAD (detached)"

    # Status
    _, status_out, _ = _run_git(["status", "--porcelain"], cwd=root)
    status_lines = [line for line in status_out.splitlines() if line.strip()]
    changed_files = []
    for line in status_lines:
        # porcelain format: XY filename
        if len(line) >= 3:
            changed_files.append(line[3:].strip())

    # Recent commits
    _, log_out, _ = _run_git(["log", "--oneline", "-10"], cwd=root)
    commits = []
    for line in log_out.splitlines():
        line = line.strip()
        if line:
            parts = line.split(" ", 1)
            commits.append(
                {
                    "hash": parts[0],
                    "message": parts[1] if len(parts) > 1 else "",
                }
            )

    return {
        "is_git": True,
        "branch": branch,
        "status_clean": len(status_lines) == 0,
        "uncommitted_count": len(status_lines),
        "changed_files": changed_files,
        "recent_commits": commits,
    }


# =============================================================================
# Journal Management
# =============================================================================


def get_latest_journal(recap_dir: Path) -> tuple[Path | None, int, int]:
    """Find the latest journal file by number.

    Returns (file_path, journal_number, line_count).
    Returns (None, 0, 0) if no journals exist.
    """
    latest_file: Path | None = None
    latest_num = -1

    for f in recap_dir.glob(f"{JOURNAL_PREFIX}*.md"):
        if not f.is_file():
            continue
        match = re.search(r"(\d+)$", f.stem)
        if match:
            num = int(match.group(1))
            if num > latest_num:
                latest_num = num
                latest_file = f

    if latest_file:
        lines = len(latest_file.read_text(encoding="utf-8").splitlines())
        return latest_file, latest_num, lines

    return None, 0, 0


def _create_journal_file(recap_dir: Path, num: int) -> Path:
    """Create a new journal file with a header."""
    new_file = recap_dir / f"{JOURNAL_PREFIX}{num}.md"
    today = datetime.now().strftime("%Y-%m-%d")

    if num == 1:
        header = f"""# Recap — Session Journal

> Auto-generated by [Recap](https://github.com/tzu-hsun/recap)
> Started: {today}

---
"""
    else:
        header = f"""# Recap — Session Journal (Part {num})

> Continuation from `{JOURNAL_PREFIX}{num - 1}.md`
> Started: {today}

---
"""
    new_file.write_text(header, encoding="utf-8")
    return new_file


def append_session(recap_dir: Path, content: str) -> Path:
    """Append session content to the latest journal, rotating if needed.

    Returns the path of the file written to.
    """
    journal_file, current_num, current_lines = get_latest_journal(recap_dir)
    content_lines = len(content.splitlines())

    if journal_file is None:
        # First journal ever
        journal_file = _create_journal_file(recap_dir, 1)
        current_lines = len(journal_file.read_text(encoding="utf-8").splitlines())

    # Rotate if appending would exceed limit
    if current_lines + content_lines > MAX_JOURNAL_LINES:
        new_num = current_num + 1 if current_num > 0 else 2
        journal_file = _create_journal_file(recap_dir, new_num)

    with journal_file.open("a", encoding="utf-8") as f:
        f.write(content)

    return journal_file


# =============================================================================
# Session Formatting
# =============================================================================


def format_session_entry(
    git_context: dict,
    summary: str,
    decisions: str = "",
    todos: str = "",
) -> str:
    """Format a session entry for the journal.

    Args:
        git_context: Output of get_git_context()
        summary: What was done this session
        decisions: Key decisions made (optional)
        todos: Outstanding items (optional)

    Returns:
        Formatted markdown string ready to append.
    """
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    lines = [f"\n\n## Session: {timestamp}\n"]

    # Branch info
    if git_context.get("is_git") and git_context.get("branch"):
        lines.append(f"**Branch**: {git_context['branch']}")
        lines.append("")

    # What was done
    lines.append("### What Was Done")
    lines.append(summary.strip() if summary.strip() else "- (no summary provided)")
    lines.append("")

    # Key decisions
    if decisions and decisions.strip():
        lines.append("### Key Decisions")
        lines.append(decisions.strip())
        lines.append("")

    # Files modified
    if git_context.get("changed_files"):
        lines.append("### Files Modified")
        for f in git_context["changed_files"]:
            lines.append(f"- {f}")
        lines.append("")

    # Recent commits
    if git_context.get("recent_commits"):
        lines.append("### Recent Commits")
        # Show up to 5 most recent
        for c in git_context["recent_commits"][:5]:
            lines.append(f"- `{c['hash']}` {c['message']}")
        lines.append("")

    # Uncommitted state
    if git_context.get("is_git"):
        if git_context.get("status_clean"):
            lines.append("### Working Directory")
            lines.append("Clean — all changes committed.")
            lines.append("")
        elif git_context.get("uncommitted_count", 0) > 0:
            lines.append("### Uncommitted Changes")
            lines.append(f"{git_context['uncommitted_count']} file(s) with uncommitted changes.")
            lines.append("")

    # TODOs
    if todos and todos.strip():
        lines.append("### TODOs")
        lines.append(todos.strip())
        lines.append("")

    lines.append("---")

    return "\n".join(lines)


def get_recent_sessions(recap_dir: Path, count: int = DEFAULT_RESTORE_COUNT) -> str:
    """Read the last N session entries from the journal(s).

    Parses entries by looking for '## Session:' headers and returns
    the most recent `count` entries as a combined string.
    """
    # Collect all journal files in order
    journal_files = sorted(
        recap_dir.glob(f"{JOURNAL_PREFIX}*.md"),
        key=lambda f: _extract_journal_num(f.name),
    )

    if not journal_files:
        return ""

    # Gather all session blocks across all journals
    all_sessions: list[str] = []

    for jf in journal_files:
        content = jf.read_text(encoding="utf-8")
        # Split on session headers
        parts = re.split(r"(?=\n## Session: )", content)
        for part in parts:
            part = part.strip()
            if part.startswith("## Session:"):
                all_sessions.append(part)

    if not all_sessions:
        return ""

    # Return last N sessions
    recent = all_sessions[-count:]
    return "\n\n".join(recent)


def _extract_journal_num(filename: str) -> int:
    """Extract journal number from filename for sorting."""
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else 0


def format_restore_context(recent_sessions: str, git_context: dict) -> str:
    """Format the context blob injected at session start.

    Combines recent session history with current git state into
    a concise restoration block.
    """
    lines = []

    # Current state
    lines.append("## Current State")
    if git_context.get("is_git"):
        lines.append(f"- **Branch**: {git_context.get('branch', 'unknown')}")
        if git_context.get("status_clean"):
            lines.append("- **Working directory**: Clean")
        else:
            lines.append(
                f"- **Working directory**: {git_context.get('uncommitted_count', 0)} uncommitted change(s)"
            )
        if git_context.get("recent_commits"):
            lines.append("- **Recent commits**:")
            for c in git_context["recent_commits"][:5]:
                lines.append(f"  - `{c['hash']}` {c['message']}")
    else:
        lines.append("- Not a git repository")

    lines.append("")

    # Previous sessions
    if recent_sessions:
        lines.append("## Previous Sessions")
        lines.append("")
        lines.append(recent_sessions)
    else:
        lines.append("## Previous Sessions")
        lines.append("No previous sessions found. This is the first session.")

    return "\n".join(lines)


def list_sessions(recap_dir: Path) -> list[dict]:
    """List all sessions with metadata.

    Returns a list of dicts with keys: timestamp, branch, file.
    """
    journal_files = sorted(
        recap_dir.glob(f"{JOURNAL_PREFIX}*.md"),
        key=lambda f: _extract_journal_num(f.name),
    )

    sessions = []
    for jf in journal_files:
        content = jf.read_text(encoding="utf-8")
        for match in re.finditer(r"## Session: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", content):
            # Try to find the branch line after this header
            pos = match.end()
            branch = None
            branch_match = re.search(r"\*\*Branch\*\*:\s*(.+)", content[pos : pos + 200])
            if branch_match:
                branch = branch_match.group(1).strip()

            sessions.append(
                {
                    "timestamp": match.group(1),
                    "branch": branch,
                    "file": jf.name,
                }
            )

    return sessions


def search_sessions(recap_dir: Path, query: str) -> list[str]:
    """Search session entries for a keyword.

    Returns matching session blocks.
    """
    journal_files = sorted(
        recap_dir.glob(f"{JOURNAL_PREFIX}*.md"),
        key=lambda f: _extract_journal_num(f.name),
    )

    results = []
    query_lower = query.lower()

    for jf in journal_files:
        content = jf.read_text(encoding="utf-8")
        parts = re.split(r"(?=\n## Session: )", content)
        for part in parts:
            part = part.strip()
            if part.startswith("## Session:") and query_lower in part.lower():
                results.append(part)

    return results


# =============================================================================
# Config
# =============================================================================


def get_config(recap_dir: Path) -> dict:
    """Read config.json, returning defaults if missing."""
    config_path = recap_dir / "config.json"
    defaults = {
        "restore_count": DEFAULT_RESTORE_COUNT,
    }
    if config_path.is_file():
        try:
            user_config = json.loads(config_path.read_text(encoding="utf-8"))
            defaults.update(user_config)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


# =============================================================================
# CLI (for direct testing)
# =============================================================================


def main() -> None:
    """Quick CLI for testing core functions."""
    import argparse

    parser = argparse.ArgumentParser(description="Recap Core — CLI test harness")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("git-context", help="Print git context as JSON")
    sub.add_parser("latest-journal", help="Show latest journal info")
    sub.add_parser("list", help="List all sessions")

    search_p = sub.add_parser("search", help="Search sessions")
    search_p.add_argument("query", help="Search term")

    restore_p = sub.add_parser("restore", help="Show restore context")
    restore_p.add_argument("--count", type=int, default=3, help="Sessions to restore")

    args = parser.parse_args()

    root = find_project_root()

    if args.command == "git-context":
        ctx = get_git_context(root)
        print(json.dumps(ctx, indent=2, ensure_ascii=False))

    elif args.command == "latest-journal":
        recap_dir = get_recap_dir(root)
        f, num, lines = get_latest_journal(recap_dir)
        print(f"File: {f}")
        print(f"Number: {num}")
        print(f"Lines: {lines}")

    elif args.command == "list":
        recap_dir = get_recap_dir(root)
        for s in list_sessions(recap_dir):
            print(f"  {s['timestamp']}  branch={s['branch']}  file={s['file']}")

    elif args.command == "search":
        recap_dir = get_recap_dir(root)
        results = search_sessions(recap_dir, args.query)
        if results:
            for r in results:
                print(r)
                print()
        else:
            print("No matching sessions found.")

    elif args.command == "restore":
        recap_dir = get_recap_dir(root)
        git_ctx = get_git_context(root)
        recent = get_recent_sessions(recap_dir, count=args.count)
        print(format_restore_context(recent, git_ctx))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
