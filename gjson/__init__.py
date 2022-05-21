"""GJSON module."""
import argparse
import json
import operator
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pkg_resources import DistributionNotFound, get_distribution


# TODO: use a proper type hint for obj once https://github.com/python/typing/issues/182 will be fixed
def get(obj: Any, query: str, *, as_str: bool = False, quiet: bool = False) -> Any:
    """Quick accessor to GJSON functionalities exposed for simplicity of use.

    Examples:
        Import and directly use this quick helper for the simpler usage::

            >>> import gjson
            >>> data = {'items': [{'name': 'a', 'size': 1}, {'name': 'b', 'size': 2}]}
            >>> gjson.get(data, 'items.#.size')
            [1, 2]

    Arguments:
        obj: the object to query. It must be accessible in JSON-like fashion so it must be an object that can be
            converted to JSON.
        query: the query string to evaluate to extract the data from the object.
        as_str: if set to :py:data:`True` returns a JSON-encoded string, a Python object otherwise.
        quiet: on error, if set to :py:data:`True`, will raises an GJSONError exception. Otherwise returns
            :py:data:`None` on error.

    Return:
        the resulting object.

    """
    gjson_obj = GJSON(obj)
    if as_str:
        return gjson_obj.getj(query, quiet=quiet)

    return gjson_obj.get(query, quiet=quiet)


class GJSON:
    """The GJSON class to operate on JSON-like objects."""

    def __init__(self, obj: Any):
        """Initialize the instance with the given object.

        Examples:
            Use the :py:class:`gjson.GJSON` class for more complex usage or to perform multiple queries on the same
            object::

                >>> import gjson
                >>> data = {'items': [{'name': 'a', 'size': 1}, {'name': 'b', 'size': 2}]}
                >>> gjson_obj = gjson.GJSON(data)

        Arguments:
            obj: the object to query.

        """
        self._obj = obj

    def __str__(self) -> str:
        """Return the current object as a JSON-encoded string.

        Examples:
            Converting to string a :py:class:`gjson.GJSON` object returns it as a JSON-encoded string::

                >>> str(gjson_obj)
                '{"items": [{"name": "a", "size": 1}, {"name": "b", "size": 2}]}'

        Returns:
            the JSON-encoded string representing the instantiated object.

        """
        return json.dumps(self._obj)

    def get(self, query: str, *, quiet: bool = False) -> Any:
        """Perform a query on the instantiated object and return the resulting object.

        Examples:
            Perform a query and get the resulting object::

                >>> gjson_obj.get('items.#.size')
                [1, 2]

        Arguments:
            query: the GJSON query to apply to the object.
            quiet: wheter to raise a :py:class:`gjson.GJSONError` exception on error or just return :py:data:`None` in
                case of error.

        Raises:
            gjson.GJSONError: on error if the quiet parameter is not :py:data:`True`.

        Returns:
            the resulting object or :py:data:`None` if the ``quiet`` parameter is :py:data:`True` and there was an
            error.

        """
        try:
            return GJSONObj(self._obj, query).get()
        except GJSONError:
            if quiet:
                return None
            raise

    def getj(self, query: str, *, quiet: bool = False) -> str:
        """Perform a query on the instantiated object and return the resulting object as JSON-encoded string.

        Examples:
            Perform a query and get the resulting object as a JSON-encoded string::

                >>> gjson_obj.getj('items.#.size')
                '[1, 2]'

        Arguments:
            query: the GJSON query to apply to the object.
            quiet: wheter to raise a :py:class:`gjson.GJSONError` exception on error or just return :py:data:`None` in
                case of error.

        Raises:
            gjson.GJSONError: on error if the quiet parameter is not :py:data:`True`.

        Returns:
            the JSON-encoded string representing the resulting object or :py:data:`None` if the ``quiet`` parameter is
            :py:data:`True` and there was an error.

        """
        try:
            return str(GJSONObj(self._obj, query))
        except GJSONError:
            if quiet:
                return ''
            raise

    def get_gjson(self, query: str, *, quiet: bool = False) -> 'GJSON':
        """Perform a query on the instantiated object and return the resulting object as a GJSON instance.

        Examples:
            Perform a query and get the resulting object already encapsulated into a :py:class:`gjson.GJSON` object::

                >>> sizes = gjson_obj.get_gjson('items.#.size')
                >>> str(sizes)
                '[1, 2]'
                >>> sizes.get('0')
                1

        Arguments:
            query: the GJSON query to apply to the object.
            quiet: wheter to raise a :py:class:`gjson.GJSONError` exception on error or just return :py:data:`None` in
                case of error.

        Raises:
            gjson.GJSONError: on error if the quiet parameter is not :py:data:`True`.

        Returns:
            the resulting object encapsulated as a :py:class:`gjson.GJSON` object or :py:data:`None` if the ``quiet``
            parameter is :py:data:`True` and there was an error.

        """
        return GJSON(self.get(query, quiet=quiet))


class GJSONError(Exception):
    """Raised by the gjson module on error while performing queries or converting to JSON."""


DOT_DELIMITER = '.'
"""str: One of the available delimiters in the query grammar."""
PIPE_DELIMITER = '|'
"""str: One of the available delimiters in the query grammar."""
# Single character operators goes last to avoid mis-detection.
QUERIES_OPERATORS = ('==', '!=', '<=', '>=', '!%', '=', '<', '>', '%')
"""tuple: The list of supported operators inside queries."""


try:
    __version__: str = get_distribution('gjson').version
    """str: the version of the current gjson module."""
except DistributionNotFound:  # pragma: no cover - this should never happen during tests
    pass  # package is not installed


class GJSONObj:
    """A low-level class to perform the GJSON query on a JSON-like object."""

    def __init__(self, obj: Any, query: str):
        """Initialize the instance with the starting object and query.

        Examples:
            Client code should not need to instantiate this low-level class in normal circumastances::

                >>> import gjson
                >>> data = {'items': [{'name': 'a', 'size': 1}, {'name': 'b', 'size': 2}]}
                >>> gjson_obj = gjson.GJSONObj(data, 'items.#.size')

        Arguments:
            obj: the JSON-like object to query.
            query: the GJSON query to apply to the object.

        """
        self._obj = obj
        self._query = query
        self._dump_params: Dict[str, Any] = {}
        self._after_hash = False
        self._after_query_all = False
        self._previous_part: Optional[str] = None

    def get(self) -> Any:
        """Perform the query and return the resulting object.

        Examples:
            Returns the resulting object::

                >>> gjson_obj.get()
                [1, 2]

        Raises:
            gjson.GJSONError: on error.

        Returns:
            the resulting object.

        """
        # Reset internal parameters
        self._dump_params = {}
        self._after_hash = False
        self._after_query_all = False
        self._previous_part = None

        if not self._query:
            raise GJSONError('Empty query.')

        query_parts = re.split(r'(?<!\\)(\.|\|)', self._query)  # negative lookbehind assertion
        delimiters = query_parts[1::2]
        path_parts = query_parts[0::2]
        obj = self._obj
        for i, part in enumerate(path_parts):
            last = (i >= (len(path_parts) - 1))
            if i > 0 and delimiters:
                delimiter = delimiters[i - 1]
            else:
                delimiter = None
            obj = self._parse_part(part, obj, delimiter, last=last)
            self._previous_part = part

        return obj

    def __str__(self) -> str:
        """Return the JSON string representation of the object, based on the query parameters.

        Examples:
            Returns the resulting object as a JSON-encoded string::

                >>> str(gjson_obj)
                '[1, 2]'

        Raises:
            gjson.GJSONError: on error.

        Returns:
            the JSON encoded string.

        """
        obj = self.get()
        prefix = self._dump_params.pop('prefix', '')
        json_string = json.dumps(obj, **self._dump_params)

        if prefix:
            json_string = '\n'.join(f'{prefix}{line}' for line in json_string.splitlines())

        return json_string

    def _parse_part(self, part: str, obj: Any, delimiter: Optional[str], *, last: bool) -> Any:  # noqa: MC0001
        """Parse the given part of the full query.

        Arguments:
            part: the query part between dots/pipes to parse.
            obj: the current object.
            delimiter: the query part delimiter (dot, pipe or None) before the current query part.
            last: whether this is the final part of the query.

        Returns:
            the result of the query.

        Raises:
            gjson.GJSONError: on invalid query.

        """
        part = part.replace(r'\.', DOT_DELIMITER).replace(r'\|', PIPE_DELIMITER)
        in_hash = False
        in_query_all = False
        ret: Any
        if part == '#':  # Hash
            in_hash = True
            if last:
                if delimiter == DOT_DELIMITER and (self._after_hash or self._after_query_all):
                    ret = []
                elif delimiter == PIPE_DELIMITER and self._previous_part == '#':
                    raise GJSONError('The pipe delimiter cannot immediately follow the # element.')
                else:
                    ret = len(obj)
            else:
                ret = obj

        elif part[0:2] == '#(':  # Queries
            if not isinstance(obj, Sequence) or isinstance(obj, (str, bytes)):
                raise GJSONError(f'Queries are supported only for sequence like objects, got {type(obj)}.')

            if part[-1] == ')':  # Return first item
                all_items = False
                suff_len = 1
            elif part[-2:] == ')#':  # Return all items
                all_items = True
                suff_len = 2
                in_query_all = True
            else:
                raise GJSONError(f'Invalid query part {part}. Expected in the format #(...) or #(...)#.')

            ret = self._parse_query(part[2:-suff_len], obj, all_items)

        elif part[0] == '@':  # Modifiers
            ret = self._parse_modifier(part, obj, last=last)

        elif re.match(r'^([1-9][0-9]*|0)$', part):  # Integer index
            if isinstance(obj, Mapping):  # Integer object keys not supported by JSON
                ret = obj[part]
            elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
                if self._after_hash:
                    if delimiter == PIPE_DELIMITER:
                        raise GJSONError('Integer query part after a pipe delimiter on an sequence like object.')
                    ret = []
                elif self._after_query_all and delimiter == DOT_DELIMITER:
                    ret = []
                else:
                    index = int(part)
                    num = len(obj)
                    if index >= num:
                        raise GJSONError(
                            f'Index {part} out of range for sequence object with {num} items in query {self._query}')
                    ret = obj[int(part)]
            else:
                raise GJSONError(f'Integer query part on unsupported object type {type(obj)}, expected a mapping '
                                 'or sequence like object.')

        elif '*' in part or '?' in part:  # Wildcards
            pattern = re.sub(r'([^\\])\*', '\\1.*', part)
            pattern = re.sub(r'([^\\])\?', '\\1.?', pattern)
            for key in obj.keys():
                if re.match(f'^{pattern}$', key):
                    ret = obj[key]
                    break
            else:
                raise GJSONError(f'No key matching pattern with wildcard {part}.')

        else:
            if not self._after_hash and isinstance(obj, Mapping):
                if part not in obj:
                    raise GJSONError(f'Mapping object does not have key {part} for query {self._query}')
                ret = obj[part]
            else:
                if delimiter and delimiter == DOT_DELIMITER:
                    ret = [i[part] for i in obj if part in i]  # Skip items without the property
                else:
                    raise GJSONError(f'Invalid or unsupported query part "{part}" for query {self._query}.')

        if in_hash:
            self._after_hash = True
        if in_query_all:
            self._after_query_all = True

        return ret

    def _parse_query(self, query: str, obj: Any, all_items: bool) -> Any:  # pylint: disable=no-self-use # noqa: MC0001
        """Parse an inline query #(...) / #(...)#.

        Arguments:
            query: the query string.
            obj: the current object.
            all_items: whether to return all items or just the first one.

        Returns:
            the result of the query.

        Raises:
            gjson.GJSONError: on invalid query.

        """
        position: Optional[int] = None
        op_str: Optional[str] = None
        for curr_op in QUERIES_OPERATORS:  # Find the first operator
            curr_pos = query.find(curr_op)
            if curr_pos == -1:
                continue
            if position is None or position > curr_pos:
                position = curr_pos
                op_str = curr_op

        if op_str is None or position is None:  # Assume check for existence of key
            ret = [i for i in obj if query in i]
            if all_items:
                return ret

            return ret[0] if ret else []

        key = query[:position].strip()
        value = json.loads(query[position + len(op_str):].strip())
        if not key and obj and isinstance(obj[0], Mapping):
            raise GJSONError('Query on mapping like objects require a key before the operator.')

        oper: Callable[[Any, Any], bool]
        if op_str in ('==', '='):
            oper = operator.eq
        elif op_str == '!=':
            oper = operator.ne
        elif op_str == '<':
            oper = operator.lt
        elif op_str == '<=':
            oper = operator.le
        elif op_str == '>':
            oper = operator.gt
        elif op_str == '>=':
            oper = operator.ge
        elif op_str in ('%', '!%'):
            value = value.replace('*', '.*').replace('?', '.?')
            value = f'^{value}$'
            if op_str == '%':
                def match_op(obj_a: Any, obj_b: Any) -> bool:
                    if not isinstance(obj_a, str):
                        return False
                    return re.match(obj_b, obj_a) is not None
                oper = match_op
            else:
                def not_match_op(obj_a: Any, obj_b: Any) -> bool:
                    if not isinstance(obj_a, str):
                        return False
                    return re.match(obj_b, obj_a) is None
                oper = not_match_op

        if key:
            ret = [i for i in obj if key in i and oper(i[key], value)]
        else:  # Query on an array of non-objects, match them directly
            ret = [i for i in obj if oper(i, value)]

        if all_items:
            return ret

        return ret[0] if ret else []

    def _parse_modifier(self, part: str, obj: Any, *, last: bool) -> Any:
        """Parse a modifier.

        Arguments:
            part: the modifier query part to parse.
            obj: the current object before applying the modifier.
            last: whether this is the final part of the query.

        Returns:
            the object modifier according to the modifier.

        Raises:
            gjson.GJSONError: in case of unknown modifier or if the modifier options are invalid.

        """
        part = part[1:]
        if ':' in part:
            modifier, options_string = part.split(':', 1)
            options = json.loads(options_string, strict=False)
            if not isinstance(options, Mapping):
                raise GJSONError(
                    f'Invalid options for modifier {modifier}, expected mapping got {type(options)}: {options}')
        else:
            modifier = part
            options = {}

        try:
            modifier_func = getattr(self, f'_parse_modifier_{modifier}')
        except AttributeError as ex:
            raise GJSONError(f'Unknown modifier {modifier}.') from ex

        return modifier_func(options, obj, last=last)

    def _parse_modifier_reverse(  # pylint: disable=no-self-use
            self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @reverse modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to reverse.
            last: whether this is the final part of the query.

        Returns:
            the reversed object. If the object cannot be reversed is returned untouched.

        """
        del last  # for pylint, unused argument
        if isinstance(obj, Mapping):
            return {k: obj[k] for k in reversed(obj.keys())}
        if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
            return obj[::-1]

        return obj

    def _parse_modifier_keys(  # pylint: disable=no-self-use
            self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @keys modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to get the keys from.
            last: whether this is the final part of the query.

        Returns:
            the current object keys as list.

        Raises:
            gjson.GJSONError: if the current object does not have a keys() method.

        """
        del last  # for pylint, unused argument
        try:
            return list(obj.keys())
        except AttributeError as ex:
            raise GJSONError('The current object does not have a keys() method.') from ex

    def _parse_modifier_values(  # pylint: disable=no-self-use
            self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @values modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to get the values from.
            last: whether this is the final part of the query.

        Returns:
            the current object values as list.

        Raises:
            gjson.GJSONError: if the current object does not have a values() method.

        """
        del last  # for pylint, unused argument
        try:
            return list(obj.values())
        except AttributeError as ex:
            raise GJSONError('The current object does not have a values() method.') from ex

    def _parse_modifier_ugly(self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @ugly modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to uglyfy.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        self._dump_params = {
            'separators': (',', ':'),
            'indent': None,
        }
        return obj

    def _parse_modifier_pretty(self, options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @pretty modifier.

        Arguments:
            options: the eventual options for the modifier.
            obj: the current object to sort.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        self._dump_params = {
            'indent': options.get('indent', 2),
            'sort_keys': options.get('sortKeys', False),
            'prefix': options.get('prefix', ''),
        }
        return obj

    def _parse_modifier_sort(  # pylint: disable=no-self-use
            self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @sort modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to sort.
            last: whether this is the final part of the query.

        Returns:
            the sorted object.

        Raises:
            gjson.GJSONError: if the current object is not sortable.

        """
        del last  # for pylint, unused argument
        if isinstance(obj, Mapping):
            return {k: obj[k] for k in reversed(obj.keys())}
        if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
            return sorted(obj)

        raise GJSONError(f'Sort modifier not supported for object of type {type(obj)}. '
                         'Expected a mapping or sequence like object.')

    def _parse_modifier_valid(  # pylint: disable=no-self-use
            self, _options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @valid modifier, checking that the current object can be converted to JSON.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element to validate.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        Raises:
            gjson.GJSONError: if the current object cannot be converted to JSON.

        """
        del last  # for pylint, unused argument
        try:
            json.dumps(obj)
        except Exception as ex:
            raise GJSONError('The current object cannot be converted to JSON.') from ex

        return obj

    def _parse_modifier_flatten(self, options: Dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @flatten modifier.

        Arguments:
            options: the eventual modifier options.
            obj: the current object to flatten.
            last: whether this is the final part of the query.

        Returns:
            the modified object.

        """
        del last  # for pylint, unused argument
        if not isinstance(obj, Sequence) or isinstance(obj, (str, bytes)):
            return obj

        return list(self._flatten_sequence(obj, deep=options.get('deep', False)))

    def _flatten_sequence(self, obj: Any, deep: bool = False) -> Any:
        """Flatten nested sequences in the given object.

        Arguments:
            obj: the current object to flatten
            deep: if :py:data:`True` recursively flatten nested sequences. By default only the first level is
                processed.

        Returns:
            the flattened object if it was a flattable sequence, the given object itself otherwise.

        """
        for elem in obj:
            if isinstance(elem, Sequence) and not isinstance(elem, (str, bytes)):
                if deep:
                    yield from self._flatten_sequence(elem, deep=deep)
                else:
                    yield from elem
            else:
                yield elem


def cli(argv: Optional[Sequence[str]] = None) -> int:
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

    try:
        if str(args.file) == '-':
            data = json.load(sys.stdin)
        else:
            with open(args.file, 'r', encoding='utf-8') as input_file:
                data = json.load(input_file)

        result = get(data, args.query, as_str=True)
        exit_code = 0
    except (json.JSONDecodeError, OSError, GJSONError) as ex:
        result = ''
        exit_code = 1
        if args.verbose == 1:
            print(f'{ex.__class__.__name__}: {ex}', file=sys.stderr)
        elif args.verbose >= 2:
            raise

    if result:
        print(result)

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
    )
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help=('Verbosity level. By default on error no output will be printed. Use -v to get the '
                              'error message to stderr and -vv to get the full traceback.'))
    parser.add_argument('file', type=Path, help='Input JSON file to query/filter. Use "-" to read from stdin.')
    parser.add_argument('query', help='A GJSON query to apply to the input data.')

    return parser
