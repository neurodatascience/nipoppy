"""Utilities for testing"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from warnings import warn

import nibabel as nib
import numpy as np
from nibabel import Nifti1Image

CONFIG_TYPE = dict[str, dict[str, list[str | int] | int]]


def _default_config() -> CONFIG_TYPE:
    """Return a config."""
    return {
        # list of possible 'datatypes'
        "fmap": {},
        "func": {
            "suffix": ["bold", "events"],
            "tasks": ["main", "rest"],
            "runs": [2, 1],  # nb runs for each task
        },
        "anat": {
            "suffix": ["t1w", "t2w"],
            "runs": [2, 1],  # nb runs for each suffix
        },
        "dwi": {"suffix": ["dwi"]},
        # other config
        "subject_folder_prefix": "sub-",
        "session_folder_prefix": "ses-",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "default_nifti_ext": ".nii.gz",
        "layout": "flat",  # flat or nested
        "filename_template": "$subject_$suffix_$task_$run_$timestamp",
    }


def create_fake_source_dataset(
    output_dir: Path = Path.cwd() / "sourcedata",
    subjects: str | int | list[str | int] = None,
    sessions: None | str | int | list[str | int | None] = None,
    datatypes: str | list[str] = None,
    config: CONFIG_TYPE | None = None,
) -> None:
    """Create a fake nifti dataset.

    The layout of the output dataset will depend on the config passed
    and the arguments passed.

    If no session is passed then there won't be a session level folder
    in the output.

    nested layouts will have subfolders for each datatype
    - sub/datatype/files

    whereas flat layouts will have all files in a single subject folder
    - sub/files

    Time stamps are added to the filenames.
    Each new session increments timestamps by one day.
    Eah new run increments timestamps by several minutes.
    """

    if subjects is None:
        subjects = ["01", "02"]
    if sessions is None:
        sessions = [""]
    if datatypes is None:
        datatypes = ["anat", "func"]
    if config is None:
        config = _default_config()

    if isinstance(subjects, (str, int)):
        subjects_to_create = [subjects]
    else:
        subjects_to_create = subjects

    if isinstance(sessions, (str, int)):
        sessions_to_create = [sessions]
    else:
        sessions_to_create = sessions

    if isinstance(datatypes, (str)):
        datatypes = [datatypes]

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()

    for sub_label in subjects_to_create:
        
        entities = {"subject": sub_label}

        timestamp = timestamp + timedelta(days=1)

        for ses_label in sessions_to_create:

            if ses_label:
                timestamp = timestamp + timedelta(days=1)
                entities["session"] = ses_label

            for datatype_ in datatypes:

                if datatype_ not in config:
                    warn(f"No datatype '{datatype_}' defined in config.", stacklevel=2)
                    continue

                entities["datatype"] = datatype_

                suffixes = config[datatype_].get("suffix")
                if not suffixes:
                    warn(
                        f"No suffixes defined in config for datatype '{datatype_}'.",
                        stacklevel=2,
                    )
                    continue

                for i_suffix, suffix_ in enumerate(config[datatype_]["suffix"]):
                    entities["suffix"] = suffix_

                    if datatype_ in ["anat", "dwi"]:
                        nb_runs = _get_nb_runs(config, datatype_, i_suffix)
                        for run in range(1, nb_runs + 1):
                            entities["run"] = run

                            entities["timestamp"] = timestamp
                            filepath = _create_file(
                                output_dir,
                                entities=entities,
                                config=config,
                            )
                            timestamp = timestamp + timedelta(minutes=10)

                    if datatype_ == "func":
                        for i_task, task in enumerate(config["func"]["tasks"]):
                            nb_runs = _get_nb_runs(config, datatype_, i_task)
                            for run in range(1, nb_runs + 1):
                                entities["task"] = task
                                entities["run"] = run
                                entities["timestamp"] = timestamp
                                filepath = _create_file(
                                    output_dir,
                                    entities=entities,
                                    config=config,
                                )
                                timestamp = timestamp + timedelta(minutes=15)
                            # _create_sidecar(filepath)

    print(f"\nDataset successfully generated in:\n{output_dir}")

    return output_dir


def _get_nb_runs(config, datatype, index):
    return config[datatype]["runs"][index] if config[datatype].get("runs") else 1


def _create_file(
    output_dir: Path,
    entities: dict[str, str | int],
    config: CONFIG_TYPE | None = None,
) -> Path:
    """Create an dummy file."""
    if config is None:
        config = _default_config()

    filename = _generate_filename(entities, config)

    filepath = output_dir / f"{config['subject_folder_prefix']}{entities['subject']}"
    if entities.get("session"):
        filepath = filepath / f"{config['session_folder_prefix']}{entities['session']}"
    if config["layout"] != "flat":
        filepath = filepath / entities["datatype"]
    filepath = filepath / filename

    filepath.parent.mkdir(parents=True, exist_ok=True)

    extension = _set_extension(entities, config)
    if extension in [".nii", ".nii.gz"]:
        image = _img_3d_rand_eye()
        if entities["datatype"] in ["func", "dwi"]:
            image = _img_4d_rand_eye()
        nib.save(image, filepath)

    return filepath


def _generate_filename(entities: dict[str, str | int], config: CONFIG_TYPE) -> str:
    subject = entities["subject"]
    timestamp = entities["timestamp"].strftime(config["timestamp_format"])
    suffix = entities["suffix"]
    run = entities.get("run")
    task = entities.get("task")

    filename = config["filename_template"]
    for t, c in zip(
        ["subject", "suffix", "timestamp", "run", "task"],
        [subject, suffix, timestamp, run, task],
    ):
        if c is None:
            filename = filename.replace(f"_${t}", "")
        else:
            filename = filename.replace(f"${t}", str(c))
    filename += _set_extension(entities, config)

    return filename


def _set_extension(entities, config):
    extension = entities.get("extension", config["default_nifti_ext"])
    if entities["suffix"] == "events":
        extension = ".tsv"
    return extension


def _create_sidecar(filepath: Path) -> None:
    """Create a sidecar JSON file."""

    metadata = {}
    with open(filepath.with_suffix(".json"), "w") as f:
        json.dump(metadata, f, indent=4)


def _rng(seed=42):
    return np.random.default_rng(seed)


def _affine_eye():
    """Return an identity matrix affine."""
    return np.eye(4)


def _shape_3d_default():
    """Return default shape for a 3D image."""
    return (10, 10, 10)


def _length_default():
    return 10


def _shape_4d_default():
    """Return default shape for a 4D image."""
    return (10, 10, 10, _length_default())


def _img_3d_rand_eye(affine=_affine_eye()):
    """Return random 3D Nifti1Image in MNI space."""
    data = _rng().random(_shape_3d_default())
    return Nifti1Image(data, affine)


def _img_4d_rand_eye(affine=_affine_eye()):
    """Return random 3D Nifti1Image in MNI space."""
    data = _rng().random(_shape_4d_default())
    return Nifti1Image(data, affine)


if __name__ == "__main__":
    create_fake_source_dataset(
        output_dir=Path.cwd() / "sourcedata",
        subjects=[
            "01",
            "02",
            "PC",
            "bob",
            "aaa",
        ],
        sessions=[1, 2],
        datatypes=["anat", "func", "dwi", "fmap", "motion"],
        config=_default_config(),
    )
