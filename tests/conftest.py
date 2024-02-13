from __future__ import annotations

import json
from pathlib import Path

import pytest
from fids.fids import create_fake_bids_dataset
from nipoppy.base import GlobalConfigs

def global_configs_file() -> Path:
    return Path(__file__).parent / "data" / "test_global_configs.json"


def global_configs_for_testing(pth: Path) -> dict:
    """Set up configuration for testing and create required directories."""
    with open(global_configs_file(), "r") as f:
        global_configs = json.load(f)

    global_configs["DATASET_ROOT"] = str(pth)

    (pth / "bids").mkdir(parents=True, exist_ok=True)

    # # make an empty dataset_description.json file
    # dataset_description = {
    #     "Name": "test",
    #     "BIDSVersion": "",
    # }
    # with open(pth / "bids" / "dataset_description.json", "w") as file_json:
    #     json.dump(dataset_description, file_json)

    create_fake_bids_dataset(output_dir=pth / "bids") # TODO this is not working

    return global_configs


@pytest.fixture(scope='function')
def global_configs_fixture(tmp_path) -> GlobalConfigs:
    return GlobalConfigs(global_configs_for_testing(tmp_path / 'dataset'))
