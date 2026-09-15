"""File operations utility functions."""

import errno
import shutil
from pathlib import Path

from nipoppy.exceptions import FileOperationError
from nipoppy.logger import get_logger
from nipoppy.utils.utils import process_template_str

logger = get_logger()

# TODO: Implement a dry-run decorator to avoid repeating dry_run checks


def mkdir(dpath: Path, dry_run=False):
    """Create a directory (including parents).

    Do nothing if the directory already exists.
    """
    if dpath.is_dir():
        return  # Directory already exists

    if dpath.exists():
        raise FileOperationError(f"Path already exists and is not a directory: {dpath}")

    logger.debug(f"Creating directory {dpath}")
    if not dry_run:
        dpath.mkdir(parents=True, exist_ok=True)


def copy(source: Path, target: Path, dry_run=False, exist_ok: bool = False):
    """
    Copy a file or directory.

    Creates missing parent directories.

    Raises
    ------
    FileOperationError
        If the target path already exists and `exist_ok` is False.
    """
    if target.exists() and not exist_ok:
        raise FileOperationError(f"Target already exists: {target}")

    mkdir(target.parent, dry_run=dry_run)
    logger.debug(f"Copying {source} to {target}")
    if not dry_run:
        if source.is_file():
            shutil.copy2(src=source, dst=target)
        else:
            shutil.copytree(src=source, dst=target, dirs_exist_ok=exist_ok)


def copy_template(
    source: Path,
    dest: Path,
    *,
    substitutions: dict,
    dry_run: bool = False,
    exist_ok: bool = False,
):
    """Copy a file with template substitution.

    Parameters
    ----------
    source
        Source template file path
    dest
        Destination file path
    substitutions
        Key-value pairs passed to process_template_str for substitution
    """
    logger.debug(f"Copying template {source} to {dest}")
    copy(source, dest, dry_run=dry_run, exist_ok=exist_ok)
    if not dry_run:
        dest.write_text(
            process_template_str(dest.read_text(), **substitutions),
        )


def movetree(source: Path, target: Path, dry_run=False):
    """Move directory tree."""
    logger.debug(f"Moving {source} to {target}")
    if not dry_run:
        mkdir(target)
        for file_path in source.iterdir():
            shutil.move(src=file_path, dst=target)
        source.rmdir()


def symlink(source: Path, target: Path, force: bool = False, dry_run=False):
    """Create a symlink: target (symlink) -> source."""
    if target.exists():
        if force:
            rm(target, dry_run=dry_run)
        else:
            raise FileOperationError(
                "Symlink target already exists. Set force=True to overwrite."
            )

    # ensure parent directory of symlink exists
    mkdir(target.parent, dry_run=dry_run)

    logger.debug(f"Creating a symlink from {target} to {source}")
    mkdir(target.parent, dry_run=dry_run)
    if not dry_run:
        target.symlink_to(source)


def _ignore_oserror_empty_dir(function, path, excinfo):
    """Ignore OSError 'Directory not empty'."""
    exception: BaseException = excinfo[1]
    if isinstance(exception, OSError) and exception.errno == errno.ENOTEMPTY:
        return
    raise exception


def rm(path: Path, dry_run=False):
    """Remove a file, directory, or symlink."""
    logger.debug(f"Removing {path}")
    if not dry_run:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path, onerror=_ignore_oserror_empty_dir)
        else:
            path.unlink()
