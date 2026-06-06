from __future__ import annotations

import argparse

from src.data_sources.fetch_bdbiar import fetch_bdbiar
from src.data_sources.fetch_boundaries import fetch_boundaries
from src.data_sources.fetch_mbis import fetch_mbis
from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.build_risk_scores import build_risk_scores
from src.pipeline.export_results import export_results
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import normalize_buildings
from src.pipeline.validate_outputs import validate_outputs
from src.utils.config import ensure_dirs, log


def build_all(force: bool = False, use_cache: bool = True, analysis_year: int | None = None, skip_network: bool = False) -> None:
    ensure_dirs()
    log("Starting build_all")
    csv_path = fetch_bdbiar(force=force, use_cache=use_cache)
    if not skip_network:
        fetch_boundaries(force=force, use_cache=use_cache)
        fetch_mbis(force=force, use_cache=use_cache)
    normalize_buildings(csv_path=csv_path, analysis_year=analysis_year)
    build_risk_scores()
    match_regulatory_notices()
    build_district_metrics()
    validate_outputs()
    export_results()
    log("build_all completed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument("--analysis-year", type=int)
    parser.add_argument("--skip-network", action="store_true")
    args = parser.parse_args()
    build_all(force=args.force, use_cache=args.use_cache, analysis_year=args.analysis_year, skip_network=args.skip_network)


if __name__ == "__main__":
    main()
