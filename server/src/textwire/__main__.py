"""``python -m textwire``: the same entry point as the ``textwire`` command."""

from textwire.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
