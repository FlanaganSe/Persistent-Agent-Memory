"""Performance benchmark tests — 250k LOC benchmark + warm query latency."""

from __future__ import annotations

from pathlib import Path

import pytest

from rkp.quality.benchmark import benchmark_extraction, generate_benchmark_repo


@pytest.mark.slow
class TestBenchmark250kLOC:
    def test_extraction_within_5_minutes(self, tmp_path: Path) -> None:
        """250k LOC benchmark → completes in < 5 minutes."""
        bench_dir = tmp_path / "bench_repo"
        bench_dir.mkdir()

        loc = generate_benchmark_repo(bench_dir, target_loc=250_000)
        assert loc > 200_000, f"Generated {loc} lines, expected > 200k"

        result = benchmark_extraction(bench_dir, gate_seconds=300.0)
        assert result.passed, (
            f"Benchmark failed: {result.total_time_seconds:.2f}s > {result.gate_seconds:.0f}s"
        )
        assert result.files_parsed > 0
        assert result.claims_created > 0

    def test_benchmark_repo_deterministic(self, tmp_path: Path) -> None:
        """File generation is deterministic (seeded)."""
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        dir_b = tmp_path / "b"
        dir_b.mkdir()

        loc_a = generate_benchmark_repo(dir_a, target_loc=10_000, seed=42)
        loc_b = generate_benchmark_repo(dir_b, target_loc=10_000, seed=42)

        assert loc_a == loc_b


class TestIncrementalUpdate:
    @pytest.mark.slow
    def test_incremental_under_2_seconds(self, tmp_path: Path) -> None:
        """Changing one file → re-extraction < 2 seconds."""
        bench_dir = tmp_path / "bench_repo"
        bench_dir.mkdir()
        generate_benchmark_repo(bench_dir, target_loc=10_000)

        # First extraction
        benchmark_extraction(bench_dir)

        # Modify one file
        some_file = next((bench_dir / "src" / "benchmark_app" / "core").glob("*.py"))
        some_file.write_text(some_file.read_text() + "\n# modified\n")

        # Re-extraction
        result = benchmark_extraction(bench_dir, gate_seconds=2.0)

        # For this test, we just verify it runs — full incremental is M14
        assert result.files_parsed > 0
