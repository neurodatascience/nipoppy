#!/usr/bin/env python
import argparse
import bids 
import json
import tarfile
import warnings
from pathlib import Path
import pandas as pd

import nipoppy.workflow.logger as my_logger
from nipoppy.trackers.tracker import Tracker, get_start_time, get_end_time, SUCCESS, UNAVAILABLE, INCOMPLETE, TRUE
from nipoppy.trackers import bids_tracker, fs_tracker, fmriprep_tracker, mriqc_tracker, tractoflow_tracker
from nipoppy.workflow.make_doughnut import run as run_make_doughnut
from nipoppy.workflow.utils import (
    BIDS_SESSION_PREFIX,
    COL_DATATYPE_MANIFEST,
    COL_SUBJECT_MANIFEST,
    COL_BIDS_ID_MANIFEST,
    COL_SESSION_MANIFEST,
    DNAME_BACKUPS_BAGEL,
    FNAME_BAGEL,
    FNAME_DOUGHNUT,
    FNAME_MANIFEST,
    load_doughnut,
    load_manifest,
    save_backup,
)

# Globals
PIPELINE_STATUS_COLUMNS = "PIPELINE_STATUS_COLUMNS"
pipeline_tracker_config_dict = {
    "heudiconv": bids_tracker.tracker_configs, 
    "freesurfer": fs_tracker.tracker_configs,
    "fmriprep": fmriprep_tracker.tracker_configs,
    "mriqc": mriqc_tracker.tracker_configs,
    "tractoflow": tractoflow_tracker.tracker_configs,
}
PIPELINE_REQUIRED_DATATYPES = {
    "heudiconv": [],
    "freesurfer": ["anat"],
    "fmriprep": ["anat"],
    "mriqc": ["anat"],
    "tractoflow": ["anat", "dwi"],
    "maget_brain": ["anat"]
}
ALL_DATATYPES = sorted(["anat", "dwi", "func", "fmap"])
BIDS_PIPES = ["mriqc","fmriprep"]
NO_TRACKER_PIPES = ["maget_brain"]

def run(global_configs, dash_schema_file, pipelines, session_id="ALL", run_id="1", acq_label=None, logger=None, log_level="INFO"):
    """ driver code running pipeline specific trackers
    """
    DATASET_ROOT = global_configs["DATASET_ROOT"]

    # load the doughnut (create a new one if needed)
    fpath_doughnut = f"{DATASET_ROOT}/scratch/raw_dicom/doughnut.csv"
    if not Path(fpath_doughnut).exists():
        warnings.warn(f"No doughnut file found, creating one at: {fpath_doughnut}")
        run_make_doughnut(global_configs, regenerate=True, empty=False)
    df_doughnut = load_doughnut(fpath_doughnut)

    # load the manifest
    fpath_manifest = f"{DATASET_ROOT}/tabular/{FNAME_MANIFEST}"
    df_manifest = load_manifest(fpath_manifest)

    # drop existing BIDS ID column if needed
    if COL_BIDS_ID_MANIFEST in df_manifest.columns:
        warnings.warn(
            f"The manifest is not supposed to have a {COL_BIDS_ID_MANIFEST} "
            "column, dropping"
        )
        df_manifest = df_manifest.drop(columns=COL_BIDS_ID_MANIFEST)

    # add BIDS ID column to the manifest
    df_manifest = df_manifest.merge(
        df_doughnut[[COL_SUBJECT_MANIFEST, COL_SESSION_MANIFEST, COL_BIDS_ID_MANIFEST]],
        on=[COL_SUBJECT_MANIFEST, COL_SESSION_MANIFEST],
        how="left",
    )

    # for bids tracker
    bids_dir = f"{DATASET_ROOT}/bids/"
    
    # logging
    log_dir = f"{DATASET_ROOT}/scratch/logs/"
    if logger is None:
        log_file = f"{log_dir}/tracker.log"
        logger = my_logger.get_logger(log_file, level=log_level)

    logger.info(f"Tracking pipelines: {pipelines}")
    logger.info(f"Tracking run: {run_id} and acq_label: {acq_label}")

    if session_id == "ALL":
        sessions = global_configs["SESSIONS"]
    else:
        sessions = [f"{BIDS_SESSION_PREFIX}{session_id}"]

    logger.info(f"Tracking session: {sessions}")    
    logger.info(f"Tracking run: {run_id} and acq_label: {acq_label}")    

    for pipeline in pipelines:
        pipe_tracker = Tracker(global_configs, dash_schema_file, pipeline) 
        
        # TODO revise tracker class
        if pipeline == "heudiconv":
            version = global_configs["BIDS"][pipeline]["VERSION"]
        else:
            version = global_configs["PROC_PIPELINES"][pipeline]["VERSION"]
            
        schema = pipe_tracker.get_dash_schema()

        if pipeline in list(pipeline_tracker_config_dict.keys()):
            tracker_configs = pipeline_tracker_config_dict[pipeline]
        else:
            logger.warning(f"Skipping pipeline: {pipeline}. Tracker not listed in the config")

        # Grab BIDS participants from the manifest
        df_manifest_imaging = df_manifest.loc[df_manifest[COL_DATATYPE_MANIFEST].apply(lambda x: len(x) != 0)]
        n_participants_with_imaging = len(df_manifest_imaging[COL_BIDS_ID_MANIFEST].unique())

        logger.info("-"*50)
        logger.info(f"pipeline: {pipeline}, version: {version}")
        logger.info(f"n_participants_with_imaging: {n_participants_with_imaging}, sessions: {sessions}")
        logger.info("-"*50)

        status_check_dict = pipe_tracker.get_pipe_tasks(tracker_configs, PIPELINE_STATUS_COLUMNS, pipeline, version)

        # only use non-prefixed columns at this stage
        # for prefixed columns we need to generate the column name
        dash_col_list = list(key for key, value in schema["GLOBAL_COLUMNS"].items() if not value["IsPrefixedColumn"])
        # status_check_dict will typically only have minimal pipeline_complete key
        for datatype in ALL_DATATYPES:
            dash_col_list.append(f"HAS_DATATYPE__{datatype}")
        dash_col_list = dash_col_list + list(status_check_dict.keys())

        for session in sessions:
            session_id = session.removeprefix(BIDS_SESSION_PREFIX)
            logger.info(f"Checking session: {session}")

            df_manifest_session = df_manifest_imaging.loc[df_manifest_imaging[COL_SESSION_MANIFEST] == session]
            participants_session = df_manifest_session[COL_BIDS_ID_MANIFEST].unique()
            n_participants_session = len(participants_session)
            logger.info(f"n_participants_session: {n_participants_session}")

            _df = pd.DataFrame(index=participants_session, columns=dash_col_list)
            _df[COL_SESSION_MANIFEST] = session
            _df["pipeline_name"] = pipeline
            _df["pipeline_version"] = version
            _df["has_mri_data"] = TRUE # everyone in participants_session has MRI data

            # Set correct dtype based on dash schema to avoid pandas warning
            # i.e. "FutureWarning: Setting an item of incompatible dtype"
            dash_col_dtype = "str"
            for dash_col, _ in status_check_dict.items():
                _df[dash_col] = _df[dash_col].astype(dash_col_dtype)
                
            # BIDS (i.e. heudiconv tracker is slightly different than proc_pipes)
            if pipeline == "heudiconv":
                # Generate BIDSLayout only once per tracker run and not for each participant
                bids_layout = bids.BIDSLayout(bids_dir, validate=False)
                logger.debug(f"bids_dir: {bids_dir}")
                logger.debug(f"bids_layout: {bids_layout.get_subjects()}")
                
            fpath_bagel = Path(DATASET_ROOT, 'derivatives', FNAME_BAGEL)
            if fpath_bagel.exists():
                df_bagel_old_full = load_bagel(fpath_bagel)

                df_bagel_old_session = df_bagel_old_full.loc[df_bagel_old_full[COL_SESSION_MANIFEST] == session]
                old_participants_session = set(df_bagel_old_session[COL_BIDS_ID_MANIFEST])
                old_pipelines_session = set(df_bagel_old_session['pipeline_name'])
                
                # make sure the number of participants is consistent across pipelines
                if set(participants_session) != old_participants_session and not old_pipelines_session.issubset(set(pipelines)):
                    warnings.warn(
                        f'The existing bagel file might be obsolete (participant list does not match the manifest file for session {session})'
                        f'. Rerun the tracker script with --pipelines {" ".join(old_pipelines_session.union(pipelines))}'
                    )
                
                df_bagel_old = df_bagel_old_full.loc[
                    ~(
                        (df_bagel_old_full["pipeline_name"] == pipeline) &
                        (df_bagel_old_full["pipeline_version"] == version) &
                        (df_bagel_old_full[COL_SESSION_MANIFEST] == session)
                    )
                ]
                
            else:
                df_bagel_old = None
            
            for bids_id, participant_id, available_datatypes in df_manifest_session[[COL_BIDS_ID_MANIFEST, COL_SUBJECT_MANIFEST, COL_DATATYPE_MANIFEST]].itertuples(index=False):
                _df.loc[bids_id, COL_SUBJECT_MANIFEST] = participant_id
                _df.loc[bids_id, COL_BIDS_ID_MANIFEST] = bids_id

                # TODO eventually we should move these to the {pipeline}_tracker.py files
                if pipeline == "heudiconv":
                    subject_dir = f"{DATASET_ROOT}/bids/{bids_id}"
                    subject_ses_dir = f"{subject_dir}/{session}"
                elif pipeline in ["freesurfer", "tractoflow"]:
                    subject_dir = f"{DATASET_ROOT}/derivatives/{pipeline}/{version}/output/{session}/{bids_id}" 
                    subject_ses_dir = subject_dir
                elif pipeline in BIDS_PIPES:
                    subject_dir = f"{DATASET_ROOT}/derivatives/{pipeline}/{version}/output/{bids_id}"
                    # NOTE temporary solution while we refactor tracker configs to be version-specific
                    if pipeline == "fmriprep":
                        subject_ses_dir = f"{subject_dir}/{session}"
                        subject_ses_tar_paths = [
                            Path(subject_ses_dir).with_suffix('.tar'),
                            Path(subject_ses_dir).with_suffix('.tar.gz'),
                        ]
                        if (
                            not Path(subject_dir).is_dir() and
                            not any([path.exists() for path in subject_ses_tar_paths])
                            ):
                            subject_dir = f"{DATASET_ROOT}/derivatives/{pipeline}/{version}/output/fmriprep/{bids_id}"
                    subject_ses_dir = f"{subject_dir}/{session}"
                elif pipeline in NO_TRACKER_PIPES:
                    logger.warning(f"pipeline: {pipeline} does not have a tracker yet...")
                else:
                    logger.error(f"unknown pipeline: {pipeline}")
                
                # populate HAS_DATATYPE__ columns
                # and check if all required datatypes are available
                required_datatypes = PIPELINE_REQUIRED_DATATYPES[pipeline]
                has_required_datatypes = True
                for datatype in ALL_DATATYPES:
                    _df.loc[bids_id, f"HAS_DATATYPE__{datatype}"] = datatype in available_datatypes
                    if (datatype in required_datatypes) and (datatype not in available_datatypes):
                        has_required_datatypes = False
                
                if has_required_datatypes:

                    subject_ses_dir_status = Path(subject_ses_dir).is_dir()
                    subject_ses_tar_paths = [
                        Path(subject_ses_dir).with_suffix('.tar'),
                        Path(subject_ses_dir).with_suffix('.tar.gz'),
                    ]
                    subject_ses_tar_status = any([path.exists() for path in subject_ses_tar_paths])
                    logger.debug(f"subject_ses_dir: {subject_ses_dir}, dir_status: {subject_ses_dir_status}, subject_ses_tar_status: {subject_ses_tar_status}")

                    if subject_ses_tar_status:
                        logger.debug(f"subject_ses_dir: {subject_ses_dir} is a tar file")
                        for name in status_check_dict.keys():
                            if name == 'pipeline_complete':
                                _df.loc[bids_id,name] = SUCCESS
                            else:
                                # here, UNAVAILABLE refers to the functionality not being implemented yet for phases/stages
                                # unrelated to pipeline_complete being UNAVAILABLE, which is related to the datatypes column in the manifest
                                _df.loc[bids_id,name] = UNAVAILABLE  # TODO check if files are available in the tar file
                            _df.loc[bids_id,"pipeline_starttime"] = UNAVAILABLE
                            _df.loc[bids_id,"pipeline_endtime"] = UNAVAILABLE
                    elif subject_ses_dir_status:
                        for name, func in status_check_dict.items():
                            if pipeline == "heudiconv":
                                status = func(bids_layout, participant_id, session_id, run_id, acq_label)
                            else:
                                status = func(subject_dir, session_id, run_id, acq_label)

                            logger.debug(f"task_name: {name}, status: {status}")                        

                            _df.loc[bids_id,name] = status
                            _df.loc[bids_id,"pipeline_starttime"] = get_start_time(subject_dir)
                            # TODO only check files listed in the tracker config
                            _df.loc[bids_id,"pipeline_endtime"] = UNAVAILABLE # get_end_time(subject_dir)
                    else:
                        logger.debug(f"{pipeline} output is expected based on manifest but not found for bids_id: {bids_id}, session: {session}")
                        for name in status_check_dict.keys():
                            _df.loc[bids_id, name] = INCOMPLETE
                        _df.loc[bids_id, "pipeline_starttime"] = UNAVAILABLE
                        _df.loc[bids_id, "pipeline_endtime"] = UNAVAILABLE
                else:
                    logger.debug(f"{pipeline} output is not expected based on manifest for bids_id: {bids_id}, session: {session}")
                    for name in status_check_dict.keys():
                        _df.loc[bids_id, name] = UNAVAILABLE
                    _df.loc[bids_id, "pipeline_starttime"] = UNAVAILABLE
                    _df.loc[bids_id, "pipeline_endtime"] = UNAVAILABLE

            _df = _df.reset_index(drop=True)

            # add old rows from other pipelines/sessions and sort for consistent order
            df_bagel: pd.DataFrame = pd.concat([df_bagel_old, _df], axis='index', ignore_index=True)
            df_bagel = df_bagel.sort_values(["pipeline_name", "pipeline_version", COL_BIDS_ID_MANIFEST, COL_SESSION_MANIFEST], ignore_index=True)

            # don't write a new file if no changes
            try:
                if (df_bagel_old is not None) and (df_bagel.shape == df_bagel_old_full.shape) and (set(df_bagel.columns) == set(df_bagel_old_full.columns)) and (len(df_bagel.compare(df_bagel_old_full)) == 0):
                    logger.info(f'No change in bagel file for pipeline {pipeline}, session {session}')
                    continue
            except Exception as exception:
                logger.warning(exception)
                pass
            
            # save bagel
            save_backup(df_bagel, fpath_bagel, DNAME_BACKUPS_BAGEL)

def load_bagel(fpath_bagel):
    def time_converter(value):
        # convert to datetime if possible
        if str(value) != UNAVAILABLE:
            return pd.to_datetime(value)
        return value
    
    df_bagel = pd.read_csv(
        fpath_bagel, 
        dtype={
            'has_mri_data': bool,
            'participant_id': str,
            'session': str,
        },
        converters={
            'pipeline_starttime': time_converter,
            'pipeline_endtime': time_converter,
        }
    )
   
    return df_bagel

if __name__ == '__main__':
    # argparse
    HELPTEXT = """
    Script to run trackers on various proc_pipes
    """
    parser = argparse.ArgumentParser(description=HELPTEXT)
    parser.add_argument('--global_config', type=str, help='path to global config file for your nipoppy dataset', required=True)
    parser.add_argument('--dash_schema', type=str, help='path to dashboard schema to display tracker status', required=True)
    parser.add_argument('--pipelines', nargs='+', help='list of pipelines to track', required=True)
    parser.add_argument('--session_id', type=str, default="ALL", help='bids session_id')
    parser.add_argument('--run_id', type=str, default="1", help='bids run_id')
    parser.add_argument('--acq_label', type=str, default=None, help='bids acq label')
    parser.add_argument('--log_level', type=str, default="INFO", help='log level')
    args = parser.parse_args()

    # read global configs
    global_config_file = args.global_config

    # Read global configs
    with open(global_config_file, 'r') as f:
        global_configs = json.load(f)
    
    # Driver code
    dash_schema_file = args.dash_schema
    pipelines = args.pipelines
    session_id = args.session_id
    run_id = args.run_id
    acq_label = args.acq_label
    log_level = args.log_level

    run(global_configs, dash_schema_file, pipelines, session_id, run_id, acq_label, log_level=log_level)
