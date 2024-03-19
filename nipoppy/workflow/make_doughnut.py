#!/usr/bin/env python

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from nipoppy.workflow.utils import (
    BIDS_SESSION_PREFIX,
    COL_BIDS_ID_MANIFEST,
    COL_CONV_STATUS,
    COL_DATATYPE_MANIFEST,
    COL_PARTICIPANT_DICOM_DIR,
    COL_DICOM_ID,
    COL_DOWNLOAD_STATUS,
    COL_ORG_STATUS,
    COL_SESSION_MANIFEST,
    COL_SUBJECT_MANIFEST,
    COLS_STATUS,
    DNAME_BACKUPS_DOUGHNUT, 
    FNAME_DOUGHNUT,
    FNAME_MANIFEST,
    load_manifest,
    participant_id_to_bids_id,
    participant_id_to_dicom_id,
    session_id_to_bids_session,
    save_backup,
)

DPATH_DOUGHNUT_RELATIVE = Path('scratch', 'raw_dicom')
FPATH_MANIFEST_RELATIVE = Path('tabular') / FNAME_MANIFEST

FLAG_EMPTY = '--empty'
FLAG_REGENERATE = '--regenerate' # TODO move this to common utils?

GLOBAL_CONFIG_DATASET_ROOT = 'DATASET_ROOT'
GLOBAL_CONFIG_SESSIONS = 'SESSIONS'

def run(global_config: dict, regenerate=False, empty=False):
    
    dpath_dataset = Path(global_config[GLOBAL_CONFIG_DATASET_ROOT])

    # generate DICOM/BIDS directory paths
    dpath_downloaded_dicom = dpath_dataset / 'scratch' / 'raw_dicom'
    dpath_organized_dicom = dpath_dataset / 'dicom'
    dpath_converted = dpath_dataset / 'bids'

    # get path to doughnut file
    fpath_doughnut_symlink = dpath_dataset / DPATH_DOUGHNUT_RELATIVE / FNAME_DOUGHNUT

    # load manifest
    fpath_manifest = dpath_dataset / FPATH_MANIFEST_RELATIVE
    df_manifest = load_manifest(fpath_manifest)

    # validate that sessions are all in global configs
    sessions_global_config = {
        session_id_to_bids_session(session)
        for session in global_config[GLOBAL_CONFIG_SESSIONS]
    }
    sessions_manifest = set(df_manifest.loc[~df_manifest[COL_SESSION_MANIFEST].isna(), COL_SESSION_MANIFEST].apply(session_id_to_bids_session))
    if not sessions_manifest.issubset(sessions_global_config):
        raise ValueError(
            f'Not all sessions in the manifest are in global config:'
            f'\n{sessions_manifest - sessions_global_config}'
        )

    # only participants with imaging data have non-empty session column
    df_doughnut = df_manifest.loc[~df_manifest[COL_SESSION_MANIFEST].isna()].copy()

    # sanity check that everyone who has session_id also has non-empty datatype list
    has_datatypes = df_doughnut.set_index(COL_SUBJECT_MANIFEST)[COL_DATATYPE_MANIFEST].apply(lambda datatypes: len(datatypes) > 0)
    participants_without_datatypes = has_datatypes.loc[~has_datatypes].index.values
    if len(participants_without_datatypes) > 0:
        raise ValueError(
            f'Some participants have a value in "{COL_SESSION_MANIFEST}" but nothing in "{COL_DATATYPE_MANIFEST}": {participants_without_datatypes}'
        )

    # look for existing doughnut file
    if fpath_doughnut_symlink.exists() and not empty:
        df_doughnut_old = pd.read_csv(fpath_doughnut_symlink, dtype=str)
    else:
        df_doughnut_old = None
        
        if (not empty) and (not regenerate):
            raise ValueError(
                f'Did not find an existing {FNAME_DOUGHNUT} file'
                f'. Use {FLAG_EMPTY} to create an empty one'
                f' or {FLAG_REGENERATE} to create one based on current files'
                ' in the dataset (can be slow)'
            )
        
    # Check for custom ID maps
    # example: participant_id --> bids_id 
    # TODO: Check if this would work for participant_id --> dicom_dir 
    if "CUSTOM_ID_MAPS" in global_config.keys():
        custom_id_maps = global_config["CUSTOM_ID_MAPS"]
        if "participant_id_to_bids_id" in custom_id_maps.keys():            
            map_file = custom_id_maps["participant_id_to_bids_id"]
            print(f"Using custom participant_id_to_bids_id mapping from: {map_file}")
    else:
        map_file = None

    # generate bids_id
    df_doughnut[COL_BIDS_ID_MANIFEST] = df_doughnut.apply(
            lambda row: participant_id_to_bids_id(
                row[COL_SUBJECT_MANIFEST],
                map_file),
            axis='columns'
        )
    
    # initialize dicom dir (cannot be inferred directly from participant id)
    df_doughnut.loc[:, COL_PARTICIPANT_DICOM_DIR] = np.nan

    # populate dicom_id
    df_doughnut.loc[:, COL_DICOM_ID] = df_doughnut[COL_SUBJECT_MANIFEST].apply(
        participant_id_to_dicom_id
    )

    # initialize all status columns
    for col in [COL_DOWNLOAD_STATUS, COL_ORG_STATUS, COL_CONV_STATUS]:
        df_doughnut[col] = False

    if regenerate:

        try:
            from nipoppy.workflow.dicom_org.dicom_dir_func import participant_id_to_dicom_dir

        except ModuleNotFoundError:
            from nipoppy.workflow.dicom_org.sample_dicom_dir_func import participant_id_to_dicom_dir
            warnings.warn(
                'Could not find participant ID -> DICOM directory conversion function, '
                'using participant_id as dicom_dir. To use a custom function, make a new file called '
                f'"dicom_dir_func.py" in {Path(__file__).parent}/dicom_org that contains a '
                'function definition for participant_id_to_dicom_dir(). '
                'See sample_dicom_dir_func.py for an example.'
            )

        df_doughnut[COL_PARTICIPANT_DICOM_DIR] = df_doughnut.apply(
            lambda row: participant_id_to_dicom_dir(
                row[COL_SUBJECT_MANIFEST],
                str(row[COL_SESSION_MANIFEST]).removeprefix(BIDS_SESSION_PREFIX),
                global_config,
            ),
            axis='columns',
        )

        # look for raw DICOM: scratch/raw_dicom/session/dicom_dir
        df_doughnut[COL_DOWNLOAD_STATUS] = check_status(
            df_doughnut, dpath_downloaded_dicom, COL_PARTICIPANT_DICOM_DIR, session_first=True,
        )

        # look for organized DICOM
        df_doughnut[COL_ORG_STATUS] = check_status(
            df_doughnut, dpath_organized_dicom, COL_DICOM_ID, session_first=True,
        )

        # look for BIDS: bids/bids_id/session
        df_doughnut[COL_CONV_STATUS] = check_status(
            df_doughnut, dpath_converted, COL_BIDS_ID_MANIFEST, session_first=False,
        )

        # warn user if there are rows with a 'True' column after one or more 'False' columns
        has_lost_files = (
            (df_doughnut[COL_CONV_STATUS] & ~(df_doughnut[COL_ORG_STATUS] | df_doughnut[COL_DOWNLOAD_STATUS])) |
            (df_doughnut[COL_ORG_STATUS] & ~df_doughnut[COL_DOWNLOAD_STATUS])
        )
        if has_lost_files.any():
            warnings.warn(
                'Some participants-session pairs seem to have lost files:'
                f'\n{df_doughnut.loc[has_lost_files]}'
            )

    else:

        df_doughnut = df_doughnut.set_index([COL_SUBJECT_MANIFEST, COL_SESSION_MANIFEST])

        if df_doughnut_old is not None:
            subject_session_pairs_old = pd.Index(zip(
                df_doughnut_old[COL_SUBJECT_MANIFEST],
                df_doughnut_old[COL_SESSION_MANIFEST],
            ))
            df_doughnut_deleted_rows = df_doughnut_old.loc[~subject_session_pairs_old.isin(df_doughnut.index)]

            # error if new doughnut file loses subject-session pairs
            if len(df_doughnut_deleted_rows) > 0:
                raise RuntimeError(
                    'Some of the subject/session pairs in the old doughnut file do not'
                    ' seem to exist anymore:'
                    f'\n{df_doughnut_deleted_rows}'
                    f'\nUse {FLAG_REGENERATE} to fully regenerate the doughnut file')
        else:
            subject_session_pairs_old = pd.Index([])

        df_doughnut_new_rows = df_doughnut.loc[~df_doughnut.index.isin(subject_session_pairs_old)]
        df_doughnut_new_rows = df_doughnut_new_rows.reset_index()[COLS_STATUS]
        df_doughnut = pd.concat([df_doughnut_old, df_doughnut_new_rows], axis='index')
        print(f'\nAdded {len(df_doughnut_new_rows)} rows to existing doughnut file')

    df_doughnut = df_doughnut[COLS_STATUS].drop_duplicates(ignore_index=True)
    df_doughnut = df_doughnut.sort_values([COL_SUBJECT_MANIFEST, COL_SESSION_MANIFEST], ignore_index=True)

    # do not write file if there are no changes from previous one
    if df_doughnut_old is not None and df_doughnut.equals(df_doughnut_old):
        print(f'\nNo change from existing doughnut file. Will not write new doughnut file.')
        return

    # save backup and make symlink
    save_backup(df_doughnut, fpath_doughnut_symlink, DNAME_BACKUPS_DOUGHNUT)

def check_status(df: pd.DataFrame, dpath, col_dname, session_first=True):

    def check_dir(dpath):
        dpath = Path(dpath)
        if dpath.exists():
            return len(list(dpath.iterdir())) > 0
        return False
    
    dpath = Path(dpath)
    status = pd.Series(np.nan, index=df.index, dtype=bool)
    for session in df[COL_SESSION_MANIFEST].drop_duplicates():
        if pd.isna(session):
            continue
        idx = (df[COL_SESSION_MANIFEST] == session)

        if session_first:
            check_func = lambda dname: check_dir(dpath / session / dname)
        else:
            check_func = lambda dname: check_dir(dpath / dname / session)

        status.loc[idx] = df[col_dname].apply(check_func)

    return status

if __name__ == '__main__':
    # argparse
    HELPTEXT = f"""
    Generate/update CSV file that tracks DICOM fetching/organization/conversion.
    """
    parser = argparse.ArgumentParser(description=HELPTEXT)
    parser.add_argument(
        '--global_config', type=str, required=True,
        help='path to global config file for your nipoppy dataset (required)')
    parser.add_argument(
        FLAG_REGENERATE, action='store_true',
        help=('regenerate entire doughnut file'
              ' (default: only append rows for new subjects/sessions)'),
    )
    parser.add_argument(
        FLAG_EMPTY, action='store_true', 
        help='generate empty doughnut file (without checking what\'s on the disk)')
    args = parser.parse_args()

    # parse
    global_config_file = args.global_config
    regenerate = getattr(args, FLAG_REGENERATE.lstrip('-'))
    empty = getattr(args, FLAG_EMPTY.lstrip('-'))

    # load global config
    with open(global_config_file) as file:
        global_config = json.load(file)

    run(global_config, regenerate=regenerate, empty=empty)
