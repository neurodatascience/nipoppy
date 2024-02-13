import json
import os

def load_json(fpath: str | os.PathLike, **kwargs) -> dict:
    """Load a JSON file.

    Parameters
    ----------
    fpath : str | os.PathLike
        Path to the JSON file

    Returns
    -------
    dict
        The JSON object.
    """
    with open(fpath) as file:
        return json.load(file, **kwargs)

def load_json_as_str(fpath: str | os.PathLike, **kwargs) -> str:
    """Load a JSON file as a string.

    Parameters
    ----------
    fpath : str | os.PathLike
        Path to the JSON file

    Returns
    -------
    str
        A string representation of the JSON object.
    """
    return json.dumps(load_json(fpath, **kwargs))
