"""Keep the report comparator's artifact intake pinned and fail-closed."""

from pathlib import Path


def test_report_comparison_uses_verified_downloads_without_failure_bypass():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    job = workflow.split("  report-reproducibility:\n", 1)[1]
    verified = "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1"
    assert job.count(verified) == 2
    assert job.count("digest-mismatch: error") == 2
    assert "needs: test" in job
    assert "continue-on-error:" not in job
    assert "github-token:" not in job  # same-run artifacts, not cross-repository intake
    assert "set -euo pipefail" in job
