from __future__ import annotations

import argparse
from pathlib import Path

import requests

from src.utils.config import RAW_DIR, SAMPLE_DIR, ensure_dirs, log, update_manifest
from src.utils.io import extract_zip

BDBIAR_URL = "https://static.csdi.gov.hk/csdi-webpage/download/0e55c533715b5da3ae0ca6e6024e90b4/csv"


def fetch_bdbiar(force: bool = False, use_cache: bool = True) -> Path:
    ensure_dirs()
    target_dir = RAW_DIR / "bdbiar"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "building_information_age_records.zip"

    existing_csvs = sorted(target_dir.glob("*.csv"))
    if use_cache and not force and existing_csvs:
        log(f"Using cached BDBIAR CSV: {existing_csvs[0]}")
        return existing_csvs[0]

    try:
        if force or not zip_path.exists():
            log("Downloading BDBIAR official data")
            response = requests.get(BDBIAR_URL, timeout=90)
            response.raise_for_status()
            zip_path.write_bytes(response.content)
        csvs = extract_zip(zip_path, target_dir)
        if not csvs:
            raise RuntimeError("BDBIAR zip did not contain a CSV file")
        csv_path = sorted(csvs, key=lambda p: p.stat().st_size, reverse=True)[0]
        update_manifest(
            "bdbiar",
            {
                "source_name": "Building information and age records",
                "provider": "Buildings Department",
                "url": BDBIAR_URL,
                "raw_file": str(csv_path),
                "zip_file": str(zip_path),
            },
        )
        log(f"BDBIAR CSV ready: {csv_path}")
        return csv_path
    except Exception as exc:
        sample = SAMPLE_DIR / "sample_buildings.csv"
        if sample.exists():
            log(f"BDBIAR download failed, using sample data: {exc}")
            update_manifest(
                "bdbiar",
                {
                    "source_name": "Sample building data",
                    "provider": "Local sample",
                    "url": "data/sample/sample_buildings.csv",
                    "raw_file": str(sample),
                    "warning": str(exc),
                },
            )
            return sample
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    fetch_bdbiar(force=args.force, use_cache=args.use_cache)


if __name__ == "__main__":
    main()
