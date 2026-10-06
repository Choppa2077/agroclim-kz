# Contributing

Thanks for looking at `agroclim`. The project is small on purpose, so the rules
are short.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Before you open a pull request

```bash
ruff check .            # linting
ruff format .           # formatting
mypy                    # strict static types
pytest                  # tests, doctests, coverage gate (85 %)
```

The same four commands run in CI, so a pull request that passes locally
normally passes on GitHub too.

## Branches and commits

- Branch from `main`: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(optimizer): add a step argument`, `fix(cli): accept dotted dates`,
  `test(model): cover the pH plateau`, `ci: cache pip downloads`.
- One logical change per commit; keep the history readable.

## Pull requests

- Reference the issue it closes (`Closes #12`).
- Describe what changed and how you checked it.
- New behaviour comes with a test; a bug fix comes with a test that fails before it.
- Agronomic constants must cite a source in `docs/methodology.md`.

## Scientific changes

Changing a modifier, a threshold or a crop constant changes published numbers.
Such a pull request must say which source supports the new value and must update
`docs/methodology.md` and the affected tests in the same change.

## Reporting problems

Use the issue templates. For a wrong recommendation, include the full command
line, the inputs and what an agronomist would have expected.
