from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.utils.config import CACHE_DIR, OUTPUTS_DIR, PROCESSED_DIR


@pytest.fixture(scope="session", autouse=True)
def restore_project_artifacts_after_tests(tmp_path_factory):
    """Keep tests from leaving sample-data artifacts in the working dashboard."""
    snapshot_root = tmp_path_factory.mktemp("artifact_snapshot")
    targets = [PROCESSED_DIR, CACHE_DIR, OUTPUTS_DIR]
    snapshots: dict[Path, Path | None] = {}

    for target in targets:
        snapshot = snapshot_root / target.name
        if target.exists():
            if target.is_dir():
                shutil.copytree(target, snapshot)
            else:
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, snapshot)
            snapshots[target] = snapshot
        else:
            snapshots[target] = None

    yield

    for target, snapshot in snapshots.items():
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if snapshot is None:
            continue
        if snapshot.is_dir():
            shutil.copytree(snapshot, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot, target)
