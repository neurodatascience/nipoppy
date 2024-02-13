from __future__ import annotations
import argparse
from pathlib import Path
from typing import Sequence

from nipoppy.base import GlobalConfigs
from nipoppy.logger import create_logger
from nipoppy.workflow.utils import BIDS_SUBJECT_PREFIX, BIDS_SESSION_PREFIX

REQUIRED_ARG = 'REQUIRED'
OPTIONAL_ARG = 'OPTIONAL'

DEFAULT_LOG_LEVEL = 'INFO'
VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

class CustomParser(argparse.ArgumentParser):

    def __init__(self, description: str | None = None, **kwargs) -> None:
        """A custom parser class with handling of logging and dry run arguments.

        Parameters
        ----------
        description : str | None, optional
            Description of the program, by default None
        """
        super().__init__(description=description, **kwargs)
        self.logger_name = None
        self.with_logging_args = False
    
    def parse_args(self, args: Sequence[str] | None = None) -> argparse.Namespace:
        """Parse arguments and create a logger if needed.

        Parameters
        ----------
        args : Sequence[str] | None
            The arguments to parse

        Returns
        -------
        argparse.Namespace
            The parsed arguments
        """
        args = super().parse_args(args=args)
        if self.with_logging_args:
            args.logger = create_logger(
                name=self.logger_name,
                fpath=args.logfile,
                level=args.log_level,
            )
            if (args.logfile is None) and args.aggregate_logs:
                args.logger.warning(
                    'aggregate_logs is True but the logger is not writing'
                    ' to a file: setting aggregate_logs to False.'
                )
                args.aggregate_logs = False
            args.logger.debug(f'Parsed arguments: {args}')
        else:
            args.logger = None
        return args

    def add_generic_optional_args(self, logger_name: str):
        """Add generic logging and dry run arguments to the parser.

        Parameters
        ----------
        logger_name : str
            Name of the logger to create.
        """
        self.add_logging_args(logger_name=logger_name)
        self.add_dry_run_arg()
    
    def add_logging_args(self, logger_name: str):
        """Add logging arguments to the parser.

        The logging arguments are: --logfile, --log-level, --aggregate-logs.

        Parameters
        ----------
        logger_name : str
            Name of the logger to create
        """
        def _log_level(log_level: str):
            log_level = log_level.upper()
            if log_level not in VALID_LOG_LEVELS:
                raise ValueError(
                    f'Invalid log level: {log_level}'
                    f'. Must be one of: {VALID_LOG_LEVELS} (case-insensitive).'
                )
            return log_level
        
        self.with_logging_args = True
        self.logger_name = logger_name

        self.add_argument(
            '--logfile',
            '--log-path',
            '--log_path',
            type=Path,
            required=False,
            help=(
                'path to log file'
                '. If not provided, the log will not be written to a file.'
            ),
        )

        self.add_argument(
            '--log-level',
            '--log_level',
            type=_log_level,
            default=DEFAULT_LOG_LEVEL,
            required=False,
            help=(
                'log level'
                f'. Must be one of: {VALID_LOG_LEVELS} (case-insensitive)'
                f'. Default: {DEFAULT_LOG_LEVEL}.'
            ),
        )

        self.add_argument(
            '--aggregate-logs',
            '--aggregate_logs',
            action='store_true',
            required=False,
            help='use a single logger for all processes.',
        )
    
    def add_dry_run_arg(self):
        """Add a --dry-run argument to the parser.
        """

        self.add_argument(
            '--dry-run',
            '--dry_run',
            action='store_true',
            required=False,
            help='print commands without actually running them.',
        )

def get_base_parser(
        description: str | None = None,
        subject: str | None = None,
        session: str | None = None,
    ) -> CustomParser:
    """Get a parser with some basic arguments.

    This returns a CustomParser with a --global-config argument and, optionally,
    --subject and/or --session arguments. It will also have methods to add
    logging and dry run arguments.

    Parameters
    ----------
    description : str | None, optional
        Description of the program, by default None
    subject : str | None, optional
        Whether to add a required or optional subject argument. Accepted values
        are "REQUIRED", "OPTIONAL", or None, by default None
    session : str | None, optional
        Whether to add a required or optional session argument. Accepted values
        are "REQUIRED", "OPTIONAL", or None, by default None

    Returns
    -------
    CustomParser
        The parser object
    """
    def check_required(arg_type):
        if arg_type not in [REQUIRED_ARG, OPTIONAL_ARG]:
            raise ValueError(
                f'Must be either {REQUIRED_ARG} or {OPTIONAL_ARG}'
                f'. Got {arg_type}'
            )
        return arg_type == 'REQUIRED'
    
    def _subject_without_prefix(subject: str):
        return subject.removeprefix(BIDS_SUBJECT_PREFIX)
    
    def _session_without_prefix(session: str):
        return session.removeprefix(BIDS_SESSION_PREFIX)
    
    parser = CustomParser(description=description)

    parser.add_argument(
        '--global-configs',
        '--global_configs',
        type=GlobalConfigs,
        help='path to global configs for a given dataset.',
    )

    if subject is not None:
        parser.add_argument(
            '--subject',
            type=_subject_without_prefix,
            required=check_required(subject),
            help=(
                f'subject ID (with or without "{BIDS_SUBJECT_PREFIX}" prefix).'
            ),
        )

    if session is not None:
        parser.add_argument(
            '--session',
            type=_session_without_prefix,
            required=check_required(session),
            help=f'session ID (with or without "{BIDS_SESSION_PREFIX}" prefix).',
        )

    return parser
