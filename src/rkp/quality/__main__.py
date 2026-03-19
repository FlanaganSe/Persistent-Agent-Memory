"""CLI entry point: python -m rkp.quality"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rkp.quality.harness import run_quality_harness


def main() -> None:
    """Run the quality harness from the command line."""
    parser = argparse.ArgumentParser(description="RKP Quality Harness")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("tests/fixtures"),
        help="Path to fixture repos directory",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to write JSON report",
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip the 250k LOC performance benchmark",
    )
    args = parser.parse_args()

    report = run_quality_harness(
        args.fixtures,
        args.report,
        skip_performance=args.skip_performance,
    )

    sys.exit(0 if report.overall_pass else 1)


if __name__ == "__main__":
    main()
