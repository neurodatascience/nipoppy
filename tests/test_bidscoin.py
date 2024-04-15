from ._utils import create_fake_source_dataset
import subprocess 
from pathlib import Path


def test_bidscoin(tmp_path):

    output_path = tmp_path
    # output_path = Path.cwd()

    rawdata = output_path / "raw"

    config = {
        "fmap": {},
        "func": {
            "suffix": ["bold", "events"],
            "tasks": ["main", "rest"],
            "runs": [2, 1],
        },
        "anat": {"suffix": ["t1w"], "runs": [2]},
        "dwi": {"suffix": ["dwi"]},
        # other config
        "subject_folder_prefix": "pd-",
        "session_folder_prefix": "",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "default_nifti_ext": ".nii.gz",
        "layout": "nested",  # flat or nested
        "filename_template": "$subject_$suffix_$task_$run_$timestamp",
    }

    sourcedata = create_fake_source_dataset(
        output_dir=output_path / "sourcedata",
        subjects=[
            "01",
            "02",
            "PC",
            "bob",
            "aaa",
        ],
        sessions=["01", "2"],
        datatypes=["anat", "func", "dwi"],
        config = config
    )

    config["subject_folder_prefix"] = "control_"
    config["filename_template"] = "$suffix_$task_$run_$timestamp"

    sourcedata = create_fake_source_dataset(
        output_dir=output_path / "sourcedata",
        subjects=[
            "01",
            "03",
            "fa",
        ],
        sessions=["01"],
        datatypes=["anat", "func"],
        config=config
    )

    CMD = f'bidsmapper {sourcedata} {rawdata} --plugins nibabel2bids --subprefix "*" --sesprefix "*" --automated --force'
    subprocess.run(CMD, capture_output=True, text=True, shell=True)

    CMD = f'bidscoiner {sourcedata} {rawdata} --force --participant_label pd-01 control_aaa control_fa'
    subprocess.run(CMD, capture_output=True, text=True, shell=True)


def test_bidscoin_enigma(tmp_path):

    output_path = tmp_path
    output_path = Path.cwd()

    rawdata = output_path / "raw"

    config = {
        "fmap": {},
        "func": {},
        "anat": {"suffix": ["t1"], "runs": [1]},
        "dwi": {},
        # other config
        "subject_folder_prefix": "COGT",
        "session_folder_prefix": "ses-",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "default_nifti_ext": ".nii.gz",
        "layout": "flat",  # flat or nested
        "filename_template": "COGT_$subject_$suffix",
    }

    sourcedata = create_fake_source_dataset(
        output_dir=output_path / "sourcedata",
        subjects=[
            "007",
            "008",
            "010",
            "013",
            "014",
            "015",
            "016",
            "017",
            "018",
            "019",
            "024",
            "026",
        ],
        sessions=["bl"],
        datatypes=["anat"],
        config = config
    )

    config["filename_template"] = "CONT_$subject_$suffix"

    sourcedata = create_fake_source_dataset(
        output_dir=output_path / "sourcedata",
        subjects=[
            "201",
            "202",
            "203",
            "204",
            "205",
            "207",
            "209",
            "210",
            "211",
            "212",
            "213",
        ],
        sessions=["bl"],
        datatypes=["anat"],
        config = config
    )    

    CMD = f'bidsmapper {sourcedata} {rawdata} --plugins nibabel2bids --subprefix "COGT" --sesprefix "ses-" --automated --force'
    subprocess.run(CMD, capture_output=True, text=True, shell=True)

    # CMD = f'bidscoiner {sourcedata} {rawdata} --force'
    # subprocess.run(CMD, capture_output=True, text=True, shell=True)    