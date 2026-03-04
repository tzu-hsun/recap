#!/usr/bin/env python3
"""Recap smoke tests — stdlib unittest, no pytest required."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts/ to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import recap_core


# ── helpers ──────────────────────────────────────────────────────────────────


def _init_git(path: Path) -> None:
    """Initialise a throwaway git repo with one commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    (path / "init.txt").write_text("init")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True)


# ── tests ────────────────────────────────────────────────────────────────────


class TestCompileCheck(unittest.TestCase):
    """Every Python file in the repo must compile without errors."""

    def test_all_python_files_compile(self):
        py_files = list(REPO_ROOT.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "No Python files found")
        for f in py_files:
            if "__pycache__" in str(f):
                continue
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                py_compile.compile(str(f), doraise=True)


class TestGitContext(unittest.TestCase):
    """get_git_context works inside and outside a git repo."""

    def test_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _init_git(tmp_path)
            ctx = recap_core.get_git_context(tmp_path)
            self.assertTrue(ctx["is_git"])
            self.assertIsNotNone(ctx["branch"])
            self.assertIsInstance(ctx["recent_commits"], list)
            self.assertGreater(len(ctx["recent_commits"]), 0)

    def test_non_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = recap_core.get_git_context(Path(tmp))
            self.assertFalse(ctx["is_git"])
            self.assertIsNone(ctx["branch"])
            self.assertEqual(ctx["changed_files"], [])


class TestJournalManagement(unittest.TestCase):
    """Journal create, append, and rotation."""

    def test_create_first_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            content = "\n## Session: 2026-01-01 10:00\nDid stuff\n---\n"
            path = recap_core.append_session(recap_dir, content)
            self.assertTrue(path.exists())
            self.assertIn("journal-1", path.name)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Session: 2026-01-01", text)

    def test_append_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            recap_core.append_session(recap_dir, "## Session: 1\nFirst\n---\n")
            path = recap_core.append_session(recap_dir, "## Session: 2\nSecond\n---\n")
            text = path.read_text(encoding="utf-8")
            self.assertIn("Session: 1", text)
            self.assertIn("Session: 2", text)

    def test_rotation_on_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            # Fill journal-1 close to the limit
            big_content = "\n".join(f"line {i}" for i in range(recap_core.MAX_JOURNAL_LINES))
            first = recap_core.append_session(recap_dir, big_content)
            first_num = int(first.stem.split("-")[-1])
            # Next append should rotate to a higher-numbered journal
            path = recap_core.append_session(recap_dir, "## Session: overflow\nExtra\n---\n")
            next_num = int(path.stem.split("-")[-1])
            self.assertGreater(next_num, first_num)


class TestSessionFormatting(unittest.TestCase):
    """format_session_entry produces valid markdown."""

    def test_with_git(self):
        ctx = {
            "is_git": True,
            "branch": "main",
            "status_clean": True,
            "uncommitted_count": 0,
            "changed_files": [],
            "recent_commits": [{"hash": "abc1234", "message": "init"}],
        }
        entry = recap_core.format_session_entry(ctx, "Set up project")
        self.assertIn("## Session:", entry)
        self.assertIn("**Branch**: main", entry)
        self.assertIn("Set up project", entry)
        self.assertIn("abc1234", entry)

    def test_without_git(self):
        ctx = {
            "is_git": False,
            "branch": None,
            "status_clean": True,
            "uncommitted_count": 0,
            "changed_files": [],
            "recent_commits": [],
        }
        entry = recap_core.format_session_entry(ctx, "Worked on docs")
        self.assertIn("## Session:", entry)
        self.assertIn("Worked on docs", entry)
        self.assertNotIn("**Branch**", entry)


class TestSessionSearch(unittest.TestCase):
    """search_sessions finds matching entries."""

    def _setup_journal(self, recap_dir: Path) -> None:
        content = (
            "## Session: 2026-01-01 10:00\nWorked on authentication\n---\n"
            "\n## Session: 2026-01-02 10:00\nFixed database migration\n---\n"
        )
        recap_core.append_session(recap_dir, content)

    def test_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            self._setup_journal(recap_dir)
            results = recap_core.search_sessions(recap_dir, "authentication")
            self.assertEqual(len(results), 1)
            self.assertIn("authentication", results[0])

    def test_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            self._setup_journal(recap_dir)
            results = recap_core.search_sessions(recap_dir, "kubernetes")
            self.assertEqual(len(results), 0)


class TestRecentSessions(unittest.TestCase):
    """get_recent_sessions returns last N entries."""

    def test_last_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            recap_dir = Path(tmp)
            entries = ""
            for i in range(5):
                entries += f"\n## Session: 2026-01-0{i + 1} 10:00\nSession {i + 1}\n---\n"
            recap_core.append_session(recap_dir, entries)
            recent = recap_core.get_recent_sessions(recap_dir, count=2)
            self.assertIn("Session 5", recent)
            self.assertIn("Session 4", recent)
            self.assertNotIn("Session 3", recent)

    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = recap_core.get_recent_sessions(Path(tmp))
            self.assertEqual(result, "")


class TestHookOutput(unittest.TestCase):
    """Both hooks produce valid JSON with hookSpecificOutput."""

    def _run_hook(self, hook_name: str, env_extra: dict | None = None) -> dict:
        hook_path = REPO_ROOT / "hooks" / hook_name
        env = os.environ.copy()
        env.update(env_extra or {})
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("hookSpecificOutput", data)
        self.assertIn("additionalContext", data["hookSpecificOutput"])
        return data

    def test_session_start_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._run_hook("on-session-start.py", {"CLAUDE_PROJECT_DIR": tmp})
            ctx = data["hookSpecificOutput"]["additionalContext"]
            self.assertIn("recap", ctx.lower())

    def test_session_end_hook(self):
        """Stop hook exits cleanly with rc=0 (Stop hooks don't support additionalContext)."""
        with tempfile.TemporaryDirectory() as tmp:
            hook_path = REPO_ROOT / "hooks" / "on-session-end.py"
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmp
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, f"Hook failed: {result.stderr}")


class TestCLI(unittest.TestCase):
    """CLI subcommands work."""

    def test_git_context_subcommand(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "recap_core.py"), "git-context"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("is_git", data)

    def test_help(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "recap_core.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Recap Core", result.stdout)


class TestConfig(unittest.TestCase):
    """get_config handles defaults, custom, and malformed files."""

    def test_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = recap_core.get_config(Path(tmp))
            self.assertEqual(cfg["restore_count"], recap_core.DEFAULT_RESTORE_COUNT)

    def test_custom(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text('{"restore_count": 5}', encoding="utf-8")
            cfg = recap_core.get_config(Path(tmp))
            self.assertEqual(cfg["restore_count"], 5)

    def test_malformed_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text("not json at all", encoding="utf-8")
            cfg = recap_core.get_config(Path(tmp))
            self.assertEqual(cfg["restore_count"], recap_core.DEFAULT_RESTORE_COUNT)


if __name__ == "__main__":
    unittest.main()
