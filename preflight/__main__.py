"""Entry point: ``python -m preflight [source|package|packaging|regression]``."""
from __future__ import annotations

import sys


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m preflight",
        description="Phoenix Validation Harness",
    )
    sub = parser.add_subparsers(dest="gate", required=True)
    sub.add_parser("source", help="Run the pre-pack gate (source mode)")
    sub.add_parser("package", help="Run the acceptance gate (package mode)")
    sub.add_parser("packaging", help="Check dist/ packaging artifacts only")
    sub.add_parser("regression", help="Regression snapshot commands")

    # Only parse the gate name here; forward the remaining args to the sub-module
    args, remaining = parser.parse_known_args()

    if args.gate == "source":
        from preflight.gates.preflight_gate import main as _main
        return _main(remaining)

    if args.gate == "package":
        from preflight.gates.acceptance_gate import main as _main
        return _main(remaining)

    if args.gate == "packaging":
        from preflight.suites.packaging import main as _main
        return _main(remaining)

    if args.gate == "regression":
        from preflight.suites.regression import main as _main
        return _main(remaining)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
