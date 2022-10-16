"""GJSON module."""
import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any, IO, Optional

from gjson import get, GJSONError


def cli(argv: Optional[Sequence[str]] = None) -> int:  # noqa: MC0001
    """Command line entry point to run gjson as a CLI tool.

    Arguments:
        argv: a sequence of CLI arguments to parse. If not set they will be read from sys.argv.

    Returns:
        The CLI exit code to use.

    Raises:
        OSError: for system-related error, including I/O failures.
        json.JSONDecodeError: when the input data is not a valid JSON.
        gjson.GJSONError: for any query-related error in gjson.

    """
    parser = get_parser()
    args = parser.parse_args(argv)

    encapsulate = False
    if args.query.startswith('..'):
        args.query = args.query[2:]
        encapsulate = True

    # Use argparse.FileType here instead of putting it as type in the --file argument parsing, to allow to handle the
    # verbosity in case of error and make sure the file is always closed in case other arguments fail the validation.
    try:
        args.file = argparse.FileType(encoding='utf-8', errors='surrogateescape')(args.file)
    except (OSError, argparse.ArgumentTypeError) as ex:
        if args.verbose == 1:
            print(f'{ex.__class__.__name__}: {ex}', file=sys.stderr)
        elif args.verbose >= 2:
            raise

        return 1

    # Reconfigure __stdin__ and __stdout__ instead of stdin and stdout because the latters are TextIO and could not
    # have the reconfigure() method if re-assigned, while reconfigure() is part of TextIOWrapper.
    # See also: https://github.com/python/typeshed/pull/8171
    sys.__stdin__.reconfigure(errors='surrogateescape')
    sys.__stdout__.reconfigure(errors='surrogateescape')

    def _execute(line: str, file_obj: Optional[IO[Any]]) -> int:
        try:
            if encapsulate:
                if line:
                    input_data = [json.loads(line)]
                elif file_obj is not None:
                    input_data = []
                    for input_line in file_obj:
                        if input_line.strip():
                            input_data.append(json.loads(input_line))
            else:
                if line:
                    input_data = json.loads(line)
                elif file_obj is not None:
                    input_data = json.load(file_obj)

            result = get(input_data, args.query, as_str=True)
            exit_code = 0
        except (json.JSONDecodeError, GJSONError) as ex:
            result = ''
            exit_code = 1
            if args.verbose == 1:
                print(f'{ex.__class__.__name__}: {ex}', file=sys.stderr)
            elif args.verbose >= 2:
                raise

        if result:
            print(result)

        return exit_code

    if args.lines:
        exit_code = 0
        for line in args.file:
            line = line.strip()
            if not line:
                continue
            ret = _execute(line, None)
            if ret > exit_code:
                exit_code = ret
    else:
        exit_code = _execute('', args.file)

    return exit_code


def get_parser() -> argparse.ArgumentParser:
    """Get the CLI argument parser.

    Returns:
        the argument parser for the CLI.

    """
    parser = argparse.ArgumentParser(
        prog='gjson',
        description=('A simple way to filter and extract data from JSON-like data structures. Python porting of the '
                     'Go GJSON package.'),
        epilog='See also the full documentation available at https://volans-.github.io/gjson-py/index.html',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help=('Verbosity level. By default on error no output will be printed. Use -v to get the '
                              'error message to stderr and -vv to get the full traceback.'))
    parser.add_argument('-l', '--lines', action='store_true',
                        help='Treat the input as JSON Lines, parse each line and apply the query to each line.')
    # argparse.FileType is used later to parse this argument.
    parser.add_argument('file', default='-', nargs='?',
                        help='Input JSON file to query. Reads from stdin if the argument is missing or set to "-".')
    parser.add_argument('query', help='A GJSON query to apply to the input data.')

    return parser
