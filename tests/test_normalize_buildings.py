from pathlib import Path

import pandas as pd

from src.pipeline.normalize_buildings import normalize_buildings
from src.utils.config import DATA_QUALITY_ISSUES_PARQUET
from src.utils.io import read_parquet


def test_normalize_sample_buildings():
    df = normalize_buildings(Path("data/sample/sample_buildings.csv"), analysis_year=2026)
    assert len(df) >= 5
    assert "building_age" in df.columns
    assert df["building_age"].notna().mean() >= 0.9
    assert set(df["risk_level"]).issubset({"Low", "Medium", "High", "Critical", "Unknown"})
    assert df["has_valid_coordinate"].mean() >= 0.8


def test_normalize_writes_data_quality_issues(tmp_path: Path):
    csv_path = tmp_path / "quality_issues.csv"
    pd.DataFrame(
        [
            {
                "building_id": "DUP1",
                "address": "1 TEST ROAD",
                "district": "Wan Chai",
                "building_use": "Commercial",
                "building_type": "Tower",
                "completion_year": 1799,
                "latitude": 22.28,
                "longitude": 114.18,
            },
            {
                "building_id": "DUP1",
                "address": "2 TEST ROAD",
                "district": "Wan Chai",
                "building_use": "",
                "building_type": "",
                "completion_year": 1980,
                "latitude": 0,
                "longitude": 0,
            },
        ]
    ).to_csv(csv_path, index=False)
    df = normalize_buildings(csv_path, analysis_year=2026)
    issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET)
    joined_flags = " ".join(issues["issue_flags"].astype(str).tolist())
    assert len(df) == 2
    assert DATA_QUALITY_ISSUES_PARQUET.exists()
    assert "duplicate_source_object_id" in joined_flags
    assert "invalid_op_date_before_1800" in joined_flags
    assert "invalid_coordinate" in joined_flags
    assert "unknown_usage" in joined_flags
