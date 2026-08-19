# Contributing

Thanks for your interest in evalite.

## Setup

```bash
git clone https://github.com/githyuvi/evalite.git
cd evalite
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,storage,server]"
```

## Running tests

```bash
pytest
```

## Making changes

- Keep pull requests focused — one change per PR is easier to review than
  several bundled together.
- Add or update tests for any behavior change.
- Match the existing code style; there's no separate style guide beyond
  what's already in the codebase.
- `main` and `develop` are protected: changes land through a reviewed,
  approved pull request, not a direct push.

## Reporting issues

Open a GitHub issue with a minimal reproduction if possible: what you ran,
what you expected, and what happened instead.
