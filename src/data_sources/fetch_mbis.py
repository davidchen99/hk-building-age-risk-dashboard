from __future__ import annotations

import argparse
from pathlib import Path

import requests

from src.utils.config import RAW_DIR, ensure_dirs, log, update_manifest

MBIS_ISSUED_URL = "https://portal.csdi.gov.hk/server/services/common/bd_rcd_1631168029910_44937/MapServer/WFSServer?service=wfs&request=GetFeature&typename=BDMBIS&outputFormat=CSV"


def fetch_mbis(force: bool = False, use_cache: bool = True) -> Path:
    ensure_dirs()
    target_dir = RAW_DIR / "mbis"
    target_dir.mkdir(parents=True, exist_ok=True)
    output = target_dir / "mbis_issued.csv"
    if use_cache and output.exists() and not force:
        log(f"Using cached MBIS CSV: {output}")
        return output
    try:
        log("Downloading MBIS issued notices")
        response = requests.get(MBIS_ISSUED_URL, timeout=90)
        response.raise_for_status()
        output.write_bytes(response.content)
        update_manifest(
            "mbis_issued",
            {
                "source_name": "Statutory Notices issued on prescribed inspection/repair for buildings",
                "provider": "Buildings Department",
                "url": MBIS_ISSUED_URL,
                "raw_file": str(output),
            },
        )
        return output
    except Exception as exc:
        log(f"MBIS download failed; continuing with empty regulatory notices: {exc}")
        update_manifest(
            "mbis_issued",
            {
                "source_name": "Statutory Notices issued on prescribed inspection/repair for buildings",
                "provider": "Buildings Department",
                "url": MBIS_ISSUED_URL,
                "warning": str(exc),
            },
        )
        return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    fetch_mbis(force=args.force, use_cache=args.use_cache)


if __name__ == "__main__":
    main()
