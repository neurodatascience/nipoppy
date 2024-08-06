"""Variable Definitions."""

import os
from typing import TypeVar

StrOrPathLike = TypeVar("StrOrPathLike", str, os.PathLike)

# BIDS
BIDS_SUBJECT_PREFIX = "sub-"
BIDS_SESSION_PREFIX = "ses-"
