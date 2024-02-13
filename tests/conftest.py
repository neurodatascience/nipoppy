from __future__ import annotations

import json
import shutil
from pathlib import Path


def _global_config_file() -> Path:
    return Path(__file__).parent / "data" / "test_global_configs.json"


def global_config_for_testing(pth: Path) -> dict:
    """Set up configuration for testing and create required directories."""
    with open(_global_config_file(), "r") as f:
        global_configs = json.load(f)

    global_configs["DATASET_ROOT"] = str(pth)

    (pth / "bids").mkdir(parents=True, exist_ok=True)

    return global_configs


def create_dummy_bids_filter(
    pth: Path, filename: str = "bids_filter.json"
) -> None:
    """Use a modified content from the tractoflow sample."""
    bids_filter = {
        "t1w": {
            "datatype": "anat",
            "session": "01",
            "run": "1",
            "suffix": "T1w",
        },
        "dwi": {"session": "01", "run": "1", "suffix": "dwi"},
    }

    pth.mkdir(parents=True, exist_ok=True)
    with open(pth / filename, "w") as f:
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
