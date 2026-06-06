from __future__ import annotations

import argparse

from src.models.risk_rules import apply_risk_scores
from src.utils.config import BUILDINGS_PARQUET, log, update_manifest
from src.utils.io import read_parquet, write_parquet


def build_risk_scores() -> None:
    df = read_parquet(BUILDINGS_PARQUET)
    scored = apply_risk_scores(df)
    write_parquet(scored, BUILDINGS_PARQUET)
    update_manifest(
        "risk_model",
        {
            "model_version": "risk_rules_v0.3_age_regulatory_combined",
            "output_file": str(BUILDINGS_PARQUET),
            "record_count": int(len(scored)),
        },
    )
    log(f"Risk scores updated for {len(scored)} buildings")


def main() -> None:
    argparse.ArgumentParser().parse_args()
    build_risk_scores()


if __name__ == "__main__":
    main()
