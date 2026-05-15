"""Earth Engine credential smoke test.

Runs a minimal Earth Engine call to confirm that the configured service
account credentials still work. Intended for local verification and weekly
GitHub Actions runs.

Usage:
    GCP_SERVICE_ACCOUNT_JSON=... EE_PROJECT_ID=... python scripts/smoke_test_ee.py

Exits with code 0 on success, non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import ee  # noqa: E402

from ee_auth import init_earth_engine  # noqa: E402


def main() -> int:
    project = init_earth_engine()
    image = ee.Image("USGS/SRTMGL1_003")
    info = image.getInfo()
    bands = [b.get("id") for b in info.get("bands", [])]
    print(f"Earth Engine OK (project={project}, bands={bands})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Earth Engine smoke test FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
