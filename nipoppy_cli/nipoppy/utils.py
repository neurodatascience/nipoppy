"""Utility functions."""

from __future__ import annotations

import datetime
import json
import os
import re
import warnings
from pathlib import Path
from typing import List, Optional, Sequence, TypeVar

import bids
import pandas as pd

StrOrPathLike = TypeVar("StrOrPathLike", str, os.PathLike)

# BIDS
BIDS_SUBJECT_PREFIX = "sub-"
BIDS_SESSION_PREFIX = "ses-"

# user configs (pipeline configs, invocations, descriptors)
TEMPLATE_REPLACE_PATTERN = re.compile("\\[\\[NIPOPPY\\_(.*?)\\]\\]")

# paths
DPATH_DATA = Path(__file__).parent / "data"
DPATH_EXAMPLES = DPATH_DATA / "examples"
FPATH_SAMPLE_CONFIG = DPATH_EXAMPLES / "sample_global_config-latest_pipelines.json"
FPATH_SAMPLE_CONFIG_FULL = DPATH_EXAMPLES / "sample_global_config-all_pipelines.json"
FPATH_SAMPLE_MANIFEST = DPATH_EXAMPLES / "sample_manifest.csv"
DPATH_INVOCATIONS = DPATH_EXAMPLES / "sample_invocations"
DPATH_TRACKER_CONFIGS = DPATH_EXAMPLES / "sample_tracker_configs"
DPATH_DESCRIPTORS = DPATH_DATA / "descriptors"
DPATH_LAYOUTS = DPATH_DATA / "layouts"
FPATH_DEFAULT_LAYOUT = DPATH_LAYOUTS / "layout-default.json"

# descriptions for common fields in the Pydantic models
FIELD_DESCRIPTION_MAP = {
    "bids_id": "BIDS-compliant participant identifier (e.g., sub-01)",
    "participant_id": "Participant identifier",
    "session": "BIDS-compliant identifier imaging session (e.g., ses-1)",
    "visit": "Visit identifier",
}


def participant_id_to_dicom_id(participant_id: str):
    """Convert a participant ID to a BIDS-compatible DICOM ID."""
    # keep only alphanumeric characters
    participant_id = str(participant_id)
    dicom_id = "".join(filter(str.isalnum, participant_id))
    return dicom_id


def dicom_id_to_bids_id(dicom_id: str):
    """Add the BIDS prefix to a DICOM ID."""
    return f"{BIDS_SUBJECT_PREFIX}{dicom_id}"


def participant_id_to_bids_id(participant_id: str):
    """Convert a participant ID to a BIDS-compatible participant ID."""
    bids_id = dicom_id_to_bids_id(participant_id_to_dicom_id(participant_id))
    return bids_id


def check_participant(participant: Optional[str]):
    """Check/process a participant string."""
    if participant is None:
        return participant

    # remove the BIDS prefix if it exists
    return str(participant).removeprefix(BIDS_SUBJECT_PREFIX)


def check_participant_id_strict(participant_id: str):
    """
    Make sure participant_id does not have the BIDS prefix.

    To use when validating user-provided files (e.g. the manifest).
    """
    if participant_id.startswith(BIDS_SUBJECT_PREFIX):
        raise ValueError(
            f'Participant ID should not start with "{BIDS_SUBJECT_PREFIX}"'
            f", got {participant_id}"
        )
    return participant_id


def check_session(session: Optional[str]):
    """Check/process a session string."""
    if session is None:
        return session

    # add BIDS prefix if it doesn't already exist
    session = str(session)
    if session.startswith(BIDS_SESSION_PREFIX):
        return session
    else:
        return f"{BIDS_SESSION_PREFIX}{session}"


def check_session_strict(session: Optional[str]):
    """
    Make sure session has the BIDS prefix.

    To use when validating user-provided files (e.g. the manifest).
    """
    if session is not None and not session.startswith(BIDS_SESSION_PREFIX):
        raise ValueError(
            f'Session should start with "{BIDS_SESSION_PREFIX}"' f", got {session}"
        )
    return session


def strip_session(session: Optional[str]):
    """Strip the BIDS prefix from a session string."""
    if session is None:
        return session
    session = str(session)
    return session.removeprefix(BIDS_SESSION_PREFIX)


def create_bids_db(
    dpath_bids: StrOrPathLike,
    dpath_bids_db: Optional[StrOrPathLike] = None,
    validate=False,
    reset_database=True,
    ignore_patterns: Optional[list[str | re.Pattern] | str | re.Pattern] = None,
    resolve_paths=True,
) -> bids.BIDSLayout:
    """Create a BIDSLayout using an indexer."""
    dpath_bids = Path(dpath_bids)
    if resolve_paths:
        dpath_bids = dpath_bids.resolve()

    if dpath_bids_db is not None:
        dpath_bids_db = Path(dpath_bids_db)

    indexer = bids.BIDSLayoutIndexer(
        validate=validate,
        ignore=ignore_patterns,
    )
    bids_layout = bids.BIDSLayout(
        root=dpath_bids,
        indexer=indexer,
        validate=validate,
        database_path=dpath_bids_db,
        reset_database=reset_database,
    )
    return bids_layout


def add_pybids_ignore_patterns(
    current: List[re.Pattern],
    new: Sequence[str | re.Pattern] | str | re.Pattern,
):
    """Add pattern(s) to ignore for PyBIDS."""
    if isinstance(new, (str, re.Pattern)):
        new = [new]
    for pattern in new:
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        if pattern not in current:
            current.append(pattern)


def get_pipeline_tag(
    pipeline_name: str,
    pipeline_version: str,
    pipeline_step: Optional[str] = None,
    participant: Optional[str] = None,
    session: Optional[str] = None,
    sep="-",
):
    """Generate a tag for a pipeline."""
    components = [pipeline_name, pipeline_version]
    if pipeline_step is not None:
        components.append(pipeline_step)
    if participant is not None:
        components.append(participant)
    if session is not None:
        components.append(strip_session(session))
    return sep.join(components)


def load_json(fpath: StrOrPathLike, **kwargs) -> dict:
    """Load a JSON file.

    Parameters
    ----------
    fpath : nipoppy.utils.StrOrPathLike
        Path to the JSON file
    **kwargs :
        Keyword arguments to pass to json.load

    Returns
    -------
    dict
        The JSON object.
    """
    with open(fpath, "r") as file:
        try:
            return json.load(file, **kwargs)
        except json.JSONDecodeError as exception:
            raise json.JSONDecodeError(
                f"Error loading JSON file at {fpath}", exception.doc, exception.pos
            )


def save_json(obj: dict, fpath: StrOrPathLike, **kwargs):
    """Save a JSON object to a file.

    Parameters
    ----------
    obj : dict
        The JSON object
    fpath : nipoppy.utils.StrOrPathLike
        Path to the JSON file to write
    indent : int, optional
        Indentation level, by default 4
    **kwargs :
        Keyword arguments to pass to json.dump
    """
    if "indent" not in kwargs:
        kwargs["indent"] = 4
    fpath = Path(fpath)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w") as file:
        json.dump(obj, file, **kwargs)


def add_path_suffix(path: StrOrPathLike, suffix: str, sep="-") -> Path:
    """Add a suffix to a path, before the last file extension (if any)."""
    path = Path(path)
    return Path(path.parent, f"{path.stem}{sep}{suffix}{path.suffix}")


def add_path_timestamp(
    path: StrOrPathLike, timestamp_format="%Y%m%d_%H%M", sep="-"
) -> Path:
    """Add a timestamp to a path, before the last file extension (if any)."""
    timestamp = datetime.datetime.now().strftime(timestamp_format)
    return add_path_suffix(path=path, suffix=timestamp, sep=sep)


def save_df_with_backup(
    df: pd.DataFrame,
    fpath_symlink: StrOrPathLike,
    dname_backups: Optional[str] = None,
    use_relative_path=True,
    dry_run=False,
    **kwargs,
) -> Path | None:
    """Save a dataframe as a symlink pointing to a timestamped "backup" file.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to save
    fpath_symlink : nipoppy.utils.StrOrPathLike
        The path to the symlink
    dname_backups : Optional[str], optional
        The directory where the timestamped backup file should be written
        (automatically determined if None), by default None
    use_relative_path : bool, optional
        Use relative instead of absolute path for the symlink, by default True
    dry_run : bool, optional
        Return the file path but do not save the file, by default False

    Returns
    -------
    Path or None
        None if no file was saved, otherwise the path to the backup file
    """
    if "index" not in kwargs:
        kwargs["index"] = False

    fpath_symlink = Path(fpath_symlink)

    fname_backup = add_path_timestamp(fpath_symlink.name)
    if dname_backups is None:
        dname_backups = f".{fpath_symlink.stem}s"

    fpath_backup_full: Path = fpath_symlink.parent / dname_backups / fname_backup

    if not dry_run:
        fpath_backup_full.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(fpath_backup_full, **kwargs)

        if use_relative_path:
            fpath_backup_to_link = os.path.relpath(
                fpath_backup_full, fpath_symlink.parent
            )
        else:
            fpath_backup_to_link = fpath_backup_full

        if fpath_symlink.is_symlink() or fpath_symlink.exists():
            fpath_symlink.unlink()
        fpath_symlink.symlink_to(fpath_backup_to_link)

    return Path(fpath_backup_full)


def process_template_str(
    template_str: str,
    resolve_paths=True,
    objs=None,
    **kwargs,
) -> str:
    """Replace template strings with values from kwargs or objects."""

    def replace(json_str: str, to_replace: str, replacement):
        if resolve_paths and isinstance(replacement, Path):
            replacement = replacement.resolve()
        return json_str.replace(to_replace, str(replacement))

    def replace_from_objs(json_str: str, to_replace: str, objs):
        for obj in objs:
            if hasattr(obj, replacement_key):
                return replace(json_str, to_replace, getattr(obj, replacement_key))
        warnings.warn(f"Unable to replace {to_replace} in {template_str_original}")
        return json_str

    if objs is None:
        objs = []

    template_str_original = template_str

    matches = TEMPLATE_REPLACE_PATTERN.finditer(template_str)
    for match in matches:
        if len(match.groups()) != 1:
            raise ValueError(f"Expected exactly one match group for match: {match}")
        to_replace = match.group()
        replacement_key = match.groups()[0].lower()  # always convert to lowercase

        if not str.isidentifier(replacement_key):
            raise ValueError(
                f"Invalid identifier name {replacement_key} in {template_str}"
            )

        if replacement_key in kwargs:
            template_str = replace(template_str, to_replace, kwargs[replacement_key])
        else:
            template_str = replace_from_objs(template_str, to_replace, objs)

    return template_str


def apply_substitutions_to_json(
    json_obj: dict | list, substitutions: dict[str, str]
) -> dict | list:
    """Apply substitutions to a JSON object."""
    # convert json_obj to string
    json_text = json.dumps(json_obj)
    for key, value in substitutions.items():
        json_text = json_text.replace(key, value)
    return json.loads(json_text)
