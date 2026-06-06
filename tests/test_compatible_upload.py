from pathlib import Path

import pandas as pd

from src.pipeline.normalize_buildings import normalize_buildings


def test_compatible_upload_schema(tmp_path: Path):
    csv_path = tmp_path / "compatible.csv"
    pd.DataFrame(
        [
            {
                "building_id": "U1",
                "address": "1 TEST ROAD",
                "district": "Wan Chai",
                "territory": "Hong Kong",
                "building_use": "Commercial",
                "building_type": "Tower",
                "completion_year": 1980,
                "latitude": 22.28,
                "longitude": 114.18,
            }
        ]
    ).to_csv(csv_path, index=False)
    df = normalize_buildings(csv_path, analysis_year=2026)
    assert df.loc[0, "source_object_id"] == "U1"
    assert df.loc[0, "building_age"] == 46
    assert df.loc[0, "usage_group"] == "Office/Commercial"
    assert df.loc[0, "type_group"] == "Tower"
    assert df.loc[0, "has_valid_coordinate"]
