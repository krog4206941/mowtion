"""python -m mowstudio opens the app. python -m mowstudio doctor runs the check."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "doctor":
        from mowstudio.doctor import run

        return run()
    from mowstudio.server import serve

    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
