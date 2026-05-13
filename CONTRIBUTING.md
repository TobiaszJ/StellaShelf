# Contributing to StellaShelf

## Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/TobiaszJ/StellaShelf.git
cd StellaShelf
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Branch Convention

| Branch | Purpose |
|---|---|
| `main` | Stable releases only |
| `develop` | Integration branch for next release |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `docs/<name>` | Documentation only |

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

feat(scanner): add XISF header extraction
fix(api): handle missing DATE-OBS gracefully
docs(readme): add quick start section
refactor(db): normalize equipment table
test(scanner): add fixtures for SGP-format FITS
chore(deps): update astropy to 7.x
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

Scopes: `scanner`, `api`, `db`, `ui`, `pipeline`, `docs`

## Pull Requests

- PRs target `develop`, not `main`
- At least one review required
- All tests must pass
- Commit messages must follow conventional commits

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=stellashelf

# Run only scanner tests
pytest tests/test_scanner.py
```

## Code Style

- Python: Ruff (linter + formatter), line length 100
- Vue: Prettier with Vue plugin
- Type hints required for all public functions

## Architecture Decisions

See [docs/architecture.md](docs/architecture.md) for design decisions and data model.