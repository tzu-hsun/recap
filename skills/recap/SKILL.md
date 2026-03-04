---
name: recap
description: >
  Session memory for Claude Code. Use when the user says /recap, asks to save
  session progress, wants to restore context from a previous session, needs to
  review past sessions, or asks about what was done previously.
---

# Recap — Session Memory

You have access to Recap, a session memory system that persists context across
Claude Code sessions. Sessions are stored as markdown journals in `.claude/recap/`.

## When to Activate

- User says `/recap` followed by a command (save, list, search)
- User asks to "save progress", "capture session", or "save what we did"
- User asks "what did we do last time?", "restore context", or "what's left to do?"
- User asks to "hand off" or prepare for a new session
- User asks to review past session history

## Commands

### `/recap save`

Capture the current session to the journal.

**Workflow:**

1. Run the git context script to get current state:
   ```bash
   python3 <plugin-root>/scripts/recap_core.py git-context
   ```

2. Summarize the current session by reviewing:
   - What was worked on (from conversation context)
   - Key decisions made and their rationale
   - Files that were created or modified
   - Any outstanding TODOs or next steps

3. Write the session entry using the script. Create the entry content as a
   temporary file, then append it:
   ```python
   # In Python, or have Claude construct the entry:
   import sys; sys.path.insert(0, '<plugin-root>/scripts')
   from recap_core import get_recap_dir, get_git_context, format_session_entry, append_session, find_project_root

   root = find_project_root()
   recap_dir = get_recap_dir(root)
   git_ctx = get_git_context(root)

   entry = format_session_entry(
       git_ctx,
       summary="- <what was done, as bullet points>",
       decisions="- <key decisions, as bullet points>",
       todos="- [ ] <outstanding items>",
   )
   path = append_session(recap_dir, entry)
   ```

4. Confirm to the user: show what was saved and where.

**Quality Gate — every save MUST include:**
- What was done (at least 2-3 bullet points)
- Files modified (from git status)
- Outstanding TODOs (even if "none")

### `/recap list`

Show recent sessions.

```bash
python3 <plugin-root>/scripts/recap_core.py list
```

Display results as a table: timestamp, branch, journal file.

### `/recap search <query>`

Search past sessions for a keyword.

```bash
python3 <plugin-root>/scripts/recap_core.py search "<query>"
```

Show matching session entries with relevant context.

### `/recap restore`

Manually restore context from previous sessions (useful if the auto-restore
hook didn't fire or the user wants to see more history).

```bash
python3 <plugin-root>/scripts/recap_core.py restore --count 3
```

Present the restored context to the user with a brief summary of:
- What was last worked on
- Outstanding TODOs
- Current git state

## Anti-Patterns

**Never capture:**
- Environment variables or `.env` file contents
- API keys, tokens, secrets, or credentials
- Full file contents (only list filenames)
- Passwords or sensitive configuration values

**Never restore:**
- Stale context without checking current git state first
- More than 5 sessions (overwhelming — default to 3)
- Sessions from a different branch without noting the branch mismatch

## Journal Format

Sessions are stored in `.claude/recap/journal-{N}.md` files. Each file is
capped at ~2000 lines. When a journal exceeds this limit, a new numbered file
is created automatically.

Example entry format:

```markdown
## Session: 2026-03-03 14:30

**Branch**: feature/auth-system

### What Was Done
- Implemented JWT authentication middleware
- Added /login and /register API endpoints

### Key Decisions
- Chose JWT over session cookies for stateless API

### Files Modified
- src/middleware/auth.ts (new)
- src/routes/auth.ts (new)

### Uncommitted Changes
2 file(s) with uncommitted changes.

### TODOs
- [ ] Add rate limiting to auth endpoints
- [ ] Write tests for auth middleware

---
```

## Tips

- Save at the end of every session, even short ones
- Include "why" in decisions, not just "what"
- TODOs should be actionable — start with a verb
- If you're handing off to another developer/session, be extra thorough
