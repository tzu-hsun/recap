# Changelog

## [1.0.0] - 2026-03-03

### Added
- Core session memory system (`scripts/recap_core.py`)
  - Git context gathering (branch, status, commits, modified files)
  - Journal management with auto-rotation at 2000 lines
  - Session formatting for save and restore
  - Session search by keyword
  - Configurable restore count
- Session start hook (`hooks/on-session-start.py`)
  - Auto-restores last N sessions on new session start
  - Graceful handling when no previous sessions exist
- Session end hook (`hooks/on-session-end.py`)
  - Captures final git state
  - Reminds to save if session wasn't captured
- Skill file (`skills/recap/SKILL.md`)
  - `/recap save` — capture current session
  - `/recap list` — show recent sessions
  - `/recap search <query>` — find past sessions
  - `/recap restore` — manually restore context
- Plugin metadata (`.claude-plugin/plugin.json`)
- Example journal with realistic entries
- Zero external dependencies — Python stdlib only
