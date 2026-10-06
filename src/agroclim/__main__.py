"""Allow ``python -m agroclim``."""

from __future__ import annotations

from agroclim.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
