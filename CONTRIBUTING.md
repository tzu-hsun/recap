# Contributing to Recap

Thanks for your interest in contributing!

## Setup

```bash
git clone https://github.com/tzu-hsun/recap.git
cd recap
pip install ruff  # for linting
```

No other dependencies — Recap uses Python stdlib only.

## Testing

```bash
python3 tests/test_smoke.py
```

All tests use `unittest` (no pytest required) and `tempfile.TemporaryDirectory()` for isolation.

## Code Style

Recap uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .           # lint
ruff format --check .  # format check
ruff format .          # auto-format
```

Configuration is in `ruff.toml`. Key rules: E, F, W, I, UP, B, SIM.

## Pull Request Process

1. Fork the repo and create a feature branch
2. Make your changes
3. Run `python3 tests/test_smoke.py` — all tests must pass
4. Run `ruff check . && ruff format --check .` — no errors
5. Open a PR against `main`

### PR Guidelines

- **No external dependencies** — Recap is stdlib-only by design
- **Add tests** for new functionality
- **Keep it simple** — Recap is intentionally minimal
- One feature per PR

## Design Principles

- Zero dependencies (Python stdlib only)
- Privacy-first (never capture secrets or file contents)
- Plain markdown storage (human-readable, git-friendly)
- Graceful degradation (works without git)
