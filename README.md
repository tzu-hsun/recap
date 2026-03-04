# Recap

[![CI](https://github.com/tzu-hsun/recap/actions/workflows/ci.yml/badge.svg)](https://github.com/tzu-hsun/recap/actions/workflows/ci.yml)

Session memory for Claude Code. Recap captures what you worked on at the end of each session and restores that context when you start a new one — so you never lose track of where you left off.

## Why Recap Exists

Claude Code is stateless. Every session starts from zero — no memory of what you built yesterday, what decisions you made, what branch you were on, or what's left to do.

Without session memory, you either:
1. **Waste the first 5-10 minutes** re-explaining context ("last time we set up auth with JWT, and we still need to add rate limiting...")
2. **Maintain HANDOFF.md files by hand** — which means remembering to write them, getting the format right, and hoping you didn't forget something
3. **Lose context entirely** — and end up re-investigating decisions that were already made

Recap fixes this with two hooks and a skill:
- A **session-start hook** that injects your recent session history into Claude's context automatically
- A **save command** (`/recap save`) that captures a structured summary when you're done
- Everything stored as **plain markdown** in your project — human-readable, grep-able, git-friendly

No external services. No databases. No dependencies beyond Python's standard library.

## Quickstart

### 1. Install the skill

Copy the self-contained skill directory into your Claude Code skills folder:

```bash
git clone https://github.com/tzu-hsun/recap.git /tmp/recap
cp -r /tmp/recap/skills/recap ~/.claude/skills/recap
rm -rf /tmp/recap
```

This installs everything Recap needs — the skill definition, hooks, and core logic — into `~/.claude/skills/recap/`. No symlinks, no repo dependency at runtime.

### 2. Add the hooks

Open your Claude Code settings file. Use the **project-level** settings for per-project memory, or **global** settings for all projects:

```bash
# Project-level (recommended — keeps history per-project)
nano .claude/settings.json

# Or global
nano ~/.claude/settings.json
```

Add the hooks configuration:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/recap/hooks/on-session-start.py",
            "timeout": 10,
            "statusMessage": "Restoring session context..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/recap/hooks/on-session-end.py",
            "timeout": 10,
            "statusMessage": "Capturing final state..."
          }
        ]
      }
    ]
  }
}

### 4. Use it

**End of session** — tell Claude:
```
/recap save
```

Claude reviews the conversation, captures what was done, key decisions, modified files, and outstanding TODOs, then writes a structured journal entry.

**Next session** — context is restored automatically. Claude starts knowing what you worked on, what's left to do, and the current git state. No re-explaining.

That's it. Two minutes to set up, works forever.

## Commands

| Command | What it does |
|---------|--------------|
| `/recap save` | Capture current session to journal (what was done, decisions, TODOs) |
| `/recap restore` | Manually restore context from previous sessions |
| `/recap list` | Show all recorded sessions with timestamps and branches |
| `/recap search <query>` | Find past sessions by keyword (e.g., `/recap search auth`) |

## What Gets Captured

Each journal entry records:

```markdown
## Session: 2026-03-03 14:30

**Branch**: feature/auth-system

### What Was Done
- Implemented JWT authentication middleware
- Added /login and /register API endpoints
- Created user model with password hashing

### Key Decisions
- Chose JWT over session cookies for stateless API
- Set token expiry to 24h with refresh token pattern

### Files Modified
- src/middleware/auth.ts (new)
- src/routes/auth.ts (new)
- src/models/user.ts (new)
- package.json (added jsonwebtoken, bcrypt)

### Uncommitted Changes
3 file(s) with uncommitted changes.

### TODOs
- [ ] Add rate limiting to auth endpoints
- [ ] Write tests for auth middleware
- [ ] Set up refresh token rotation

---
```

### What never gets captured

Recap is privacy-first by design. It never records:

- Environment variables or `.env` file contents
- API keys, tokens, secrets, or credentials
- Full file contents (only filenames are listed)
- Passwords or sensitive configuration values

The journal only contains git metadata (branch, status, commit messages) and summaries written by Claude from the conversation — never raw file contents.

## How It Works

### The save/restore loop

```
Session 1                          Session 2
┌─────────────────────┐            ┌─────────────────────┐
│  You work with      │            │  Hook fires on      │
│  Claude as usual    │            │  session start       │
│                     │            │         │            │
│  At the end:        │            │         ▼            │
│  /recap save        │            │  Last 3 sessions     │
│         │           │            │  injected into       │
│         ▼           │            │  Claude's context    │
│  Journal entry      │───────────▶│                     │
│  written to         │            │  Claude already      │
│  .claude/recap/     │            │  knows what you      │
│                     │            │  worked on           │
└─────────────────────┘            └─────────────────────┘
```

### Storage

Sessions are stored as markdown journals inside your project:

```
your-project/
└── .claude/
    └── recap/
        ├── journal-1.md      # Session entries (auto-rotating)
        ├── journal-2.md      # Created when journal-1 exceeds 2000 lines
        └── config.json       # Optional user preferences
```

- **Per-project** — each project has its own session history
- **Git-friendly** — commit the journals to share context with your team, or `.gitignore` them to keep history private
- **Auto-rotating** — journals are capped at ~2000 lines; when one fills up, a new numbered file is created automatically

### The two hooks

**`on-session-start.py`** — Fires when Claude Code starts. Reads the last few journal entries and current git state, then injects a concise context summary into Claude's session via `hookSpecificOutput.additionalContext`. If no journals exist yet, it shows a brief intro message.

**`on-session-end.py`** — Fires when Claude Code stops. Captures the final git state (branch, uncommitted changes) and reminds about `/recap save` if the session wasn't captured yet.

### The skill

The `SKILL.md` file teaches Claude how to respond to `/recap` commands. When you say `/recap save`, Claude:

1. Gathers the current git context (branch, status, commits, modified files)
2. Reviews the conversation to summarize what was done
3. Identifies key decisions and their rationale
4. Lists outstanding TODOs
5. Appends a formatted markdown entry to the journal
6. Confirms what was saved and where

## Configuration

Create `.claude/recap/config.json` in your project to customize behavior:

```json
{
  "restore_count": 3
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `restore_count` | `3` | Number of recent sessions to restore on session start |

Setting `restore_count` to `1` gives minimal context (just the last session). Setting it to `5` gives more history but uses more of Claude's context window.

## Project Structure

```
recap/
├── skills/
│   └── recap/                        # Self-contained — copy this to ~/.claude/skills/recap/
│       ├── SKILL.md                  # Skill definition (teaches Claude the /recap commands)
│       ├── hooks/
│       │   ├── on-session-start.py   # Auto-restore context on session start
│       │   └── on-session-end.py     # Capture final state on session end
│       └── scripts/
│           └── recap_core.py         # Core logic (git context, journal management)
├── tests/
│   └── test_smoke.py                 # Test suite (unittest, no pytest)
├── examples/
│   └── sample-journal.md             # Example of what journal entries look like
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE                           # MIT
└── .gitignore
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Python stdlib only** | No `pip install`. Works on any machine with Python 3.9+. Maximum portability. |
| **Per-project storage** | Session history is project-specific. You don't want your auth system notes leaking into your portfolio project. |
| **Markdown journals** | Human-readable without tools. Works with `grep`, `cat`, any editor. Diffs cleanly in git. |
| **2000-line rotation** | Prevents unbounded file growth. Old journals remain accessible but don't bloat the active file. |
| **Concise restore (last 3 sessions)** | Enough context to resume work without flooding Claude's context window. Configurable if you need more or less. |
| **Privacy-first** | Only git metadata and user-written summaries. Never env vars, secrets, or file contents. |
| **Graceful degradation** | Works without git (just captures summaries). Works without hooks (manual `/recap save`). |

## Requirements

- Python 3.9+
- Claude Code CLI
- Git (optional — works without it, just captures less context)

## FAQ

**Q: Does it work without git?**
Yes. Without git, Recap skips branch/commit/status info and just captures the session summary, decisions, and TODOs.

**Q: Can I share session history with my team?**
Yes. Commit the `.claude/recap/` directory to your repo. Anyone who pulls will have the session history available when they start Claude Code.

**Q: How much of Claude's context window does the restore use?**
Minimal. The default restores 3 sessions, typically 50-150 lines of concise markdown. You can reduce it to 1 session via `config.json` if context is tight.

**Q: What if I forget to `/recap save`?**
The session-end hook will remind you. You can also run `/recap save` at the start of your next session to capture what you remember (though the git state will reflect the current state, not the previous session's).

**Q: Can I edit journal entries?**
Yes. They're plain markdown files. Open `.claude/recap/journal-1.md` in any editor and modify as needed.

## License

MIT
