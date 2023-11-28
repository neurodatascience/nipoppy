from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


def _global_config_file() -> Path:
    return Path(__file__).parent / "data" / "test_global_configs.json"


def global_config_for_testing(pth: Path) -> dict:
    """Set up configuration for testing and create required directories."""
    with open(_global_config_file(), "r") as f:
        global_configs = json.load(f)

    global_configs["DATASET_ROOT"] = str(pth)

    (pth / "bids").mkdir(parents=True, exist_ok=True)

    return global_configs


@pytest.fixture
def dummy_bids_filter(tmp_path) -> None:
    create_dummy_bids_filter(tmp_path)


def create_dummy_bids_filter(pth: Path) -> None:
    bids_filter = {
        "t1w": {
            "datatype": "anat",
            "session": "01",
            "suffix": "T1w"
        }
    }
    with open(pth / "bids_filter.json", "w") as f:
        json.dump(bids_filter, f)


def mock_bids_dataset(pth: Path, dataset: str) -> Path:
    """Copy a BIDS example dataset to the given path."""
    ds = Path(__file__).parent / "data" / dataset
    print(f"\nCopying {ds} to {pth}\n")
    shutil.copytree(
        ds,
        pth,
        symlinks=True,
        ignore_dangling_symlinks=True,
        dirs_exist_ok=True,
    )

    return pth / "bids"
