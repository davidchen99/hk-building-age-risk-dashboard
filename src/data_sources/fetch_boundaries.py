from __future__ import annotations

import argparse
from pathlib import Path

import requests

from src.utils.config import RAW_DIR, ensure_dirs, log, update_manifest

DISTRICT_BOUNDARY_URL = "https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json"


def fetch_boundaries(force: bool = False, use_cache: bool = True) -> Path:
    ensure_dirs()
    target_dir = RAW_DIR / "district_boundary"
    target_dir.mkdir(parents=True, exist_ok=True)
    output = target_dir / "hksar_18_district_boundary.json"
    if use_cache and output.exists() and not force:
        log(f"Using cached district boundary JSON: {output}")
        return output
    try:
        log("Downloading district boundary JSON")
        response = requests.get(DISTRICT_BOUNDARY_URL, timeout=60)
        response.raise_for_status()
        output.write_bytes(response.content)
        update_manifest(
            "district_boundary",
            {
                "source_name": "District boundary",
                "provider": "Home Affairs Department",
                "url": DISTRICT_BOUNDARY_URL,
                "raw_file": str(output),
            },
        )
        return output
    except Exception as exc:
        log(f"District boundary download failed; continuing without boundary file: {exc}")
        update_manifest(
            "district_boundary",
            {
                "source_name": "District boundary",
                "provider": "Home Affairs Department",
                "url": DISTRICT_BOUNDARY_URL,
                "warning": str(exc),
            },
        )
        return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    fetch_boundaries(force=args.force, use_cache=args.use_cache)


if __name__ == "__main__":
    main()
