"""GJSON module."""
import json
import operator
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Optional, Union

from gjson._protocols import ModifierProtocol
from gjson.exceptions import GJSONError, GJSONInvalidSyntaxError, GJSONParseError

ESCAPE_CHARACTER = '\\'
"""str: The grammar escape character."""
DOT_DELIMITER = '.'
"""str: One of the available delimiters in the query grammar."""
PIPE_DELIMITER = '|'
"""str: One of the available delimiters in the query grammar."""
DELIMITERS = (DOT_DELIMITER, PIPE_DELIMITER)
"""tuple: All the available delimiters in the query grammar."""
MULTIPATHS_DELIMITERS = DELIMITERS + (']', '}', ',')
"""tuple: All the available delimiters in the query grammar."""
# Single character operators goes last to avoid mis-detection.
QUERIES_OPERATORS = ('==~', '==', '!=', '<=', '>=', '!%', '=', '<', '>', '%')
"""tuple: The list of supported operators inside queries."""
MODIFIER_NAME_RESERVED_CHARS = ('"', ',', '.', '|', ':', '@', '{', '}', '[', ']', '(', ')')
"""tuple: The list of reserver characters not usable in a modifier's name."""
PARENTHESES_PAIRS = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{'}


class NoResult:
    """A no result type to be passed around and be checked."""


@dataclass
class BaseQueryPart:
    """Base dataclass class to represent a query part."""

    start: int
    end: int
    part: str
    delimiter: str
    previous: Optional['BaseQueryPart']
    is_last: bool

    def __str__(self) -> str:
        """String representation of the part.

        Returns:
            The part property of the instance.

        """
        return self.part


class FieldQueryPart(BaseQueryPart):
    """Basic field path query part."""


class ArrayLenghtQueryPart(BaseQueryPart):
    """Hash query part, to get the size of an array."""


class ArrayIndexQueryPart(BaseQueryPart):
    """Integer query part to get an array index."""

    @property
    def index(self) -> int:
        """Return the integer representation of the query part.

        Returns:
            the index as integer.

        """
        return int(self.part)


@dataclass
class ArrayQueryQueryPart(BaseQueryPart):
    """Query part for array queries, with additional fields."""

    field: str
    operator: str
    value: Union[str, 'ArrayQueryQueryPart']
    first_only: bool


@dataclass
class ModifierQueryPart(BaseQueryPart):
    """Modifier query part."""

    name: str
    options: dict[Any, Any]


@dataclass
class MultipathsItem:
    """Single multipaths query item."""

    key: str
    values: list[BaseQueryPart]


@dataclass
class MultipathsObjectQueryPart(BaseQueryPart):
    """JSON object multipaths query part."""

    parts: list[MultipathsItem]


@dataclass
class MultipathsArrayQueryPart(BaseQueryPart):
    """JSON object multipaths query part."""

    parts: list[list[BaseQueryPart]]


class LiteralQueryPart(BaseQueryPart):
    """Literal query part."""


class GJSONObj:
    """A low-level class to perform the GJSON query on a JSON-like object."""

    # pylint: disable=too-many-branches,too-many-statements,too-many-locals

    def __init__(self, obj: Any, query: str, *, custom_modifiers: Optional[dict[str, ModifierProtocol]] = None):
        """Initialize the instance with the starting object and query.

        Examples:
            Client code should not need to instantiate this low-level class in normal circumastances::

                >>> import gjson
                >>> data = {'items': [{'name': 'a', 'size': 1}, {'name': 'b', 'size': 2}]}
                >>> gjson_obj = gjson.GJSONObj(data, 'items.#.size')

        Arguments:
            obj: the JSON-like object to query.
            query: the GJSON query to apply to the object.
            custom_modifiers: an optional dictionary with the custom modifiers to load. The dictionary keys are the
                names of the modifiers and the values are the callables with the modifier code that adhere to the
                :py:class:`gjson.ModifierProtocol` protocol.

        Raises:
            gjson.GJSONError: if any provided custom modifier overrides a built-in one or is not callable.

        """
        self._obj = obj
        self._query = query
        if custom_modifiers is not None:
            if (intersection := self.builtin_modifiers().intersection(set(custom_modifiers.keys()))):
                raise GJSONError(f'Some provided custom_modifiers have the same name of built-in ones: {intersection}.')

            for name, modifier in custom_modifiers.items():
                if not isinstance(modifier, ModifierProtocol):
                    raise GJSONError(f'The given func "{modifier}" for the custom modifier @{name} does not adhere '
                                     'to the gjson.ModifierProtocol.')

        self._custom_modifiers = custom_modifiers if custom_modifiers else {}
        self._dump_params: dict[str, Any] = {'ensure_ascii': False}
        self._after_hash = False
        self._after_query_all = False

    @classmethod
    def builtin_modifiers(cls) -> set[str]:
        """Return the names of the built-in modifiers.

        Returns:
            the names of the built-in modifiers.

        """
        prefix = '_apply_modifier_'
        return {modifier[len(prefix):] for modifier in dir(cls) if modifier.startswith(prefix)}

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
        self._dump_params = {'ensure_ascii': False}
        self._after_hash = False
        self._after_query_all = False

        if not self._query:
            raise GJSONError('Empty query.')

        obj = self._obj
        for part in self._parse(start=0, end=len(self._query) - 1):
            obj = self._parse_part(part, obj)

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

    def _parse(self, *, start: int, end: int, max_end: int = 0, delimiter: str = '',
               in_multipaths: bool = False) -> list[BaseQueryPart]:
        """Main parser of the query that will delegate to more specific parsers for each different feature.

        Arguments:
            start: the start position in the query.
            end: the end position in the query.
            max_end: an optional last position up to where a closing parentheses can be searched.
            delimiter: the optional delimiter before the query, if this is called on a multipaths.
            in_multipaths: whether the part to be parsed is inside a multipaths.

        Raises:
            gjson.GJSONParseError: on error.

        Returns:
            the resulting object.

        """
        current: list[str] = []
        current_start = -1
        parts: list[BaseQueryPart] = []
        previous: Optional[BaseQueryPart] = None
        require_delimiter = False

        i = start
        while True:
            part: Optional[BaseQueryPart] = None
            # Get current and next character in the query
            if i == end:
                next_char = None
            elif i >= end:
                if parts and not current:
                    parts[-1].is_last = True
                break
            else:
                next_char = self._query[i + 1]

            char = self._query[i]

            if char in DELIMITERS:
                if i == start:
                    raise GJSONParseError('Invalid query starting with a path delimiter.',
                                          query=self._query, position=i)

                if next_char in DELIMITERS:
                    raise GJSONParseError('Invalid query with two consecutive path delimiters.',
                                          query=self._query, position=i)
                if current:
                    part = FieldQueryPart(start=current_start, end=i - 1, part=''.join(current),
                                          delimiter=delimiter, previous=previous, is_last=False)
                    parts.append(part)
                    previous = part
                    current = []
                    current_start = -1

                delimiter = char
                require_delimiter = False
                if next_char is None:
                    raise GJSONParseError('Delimiter at the end of the query.', query=self._query, position=i)

                i += 1
                continue

            if char == '@':
                part = self._parse_modifier_query_part(i, delimiter, max_end=max_end, in_multipaths=in_multipaths)
            elif char == '#' and (next_char in DELIMITERS or next_char is None):
                part = ArrayLenghtQueryPart(start=i, end=i, part=char, delimiter=delimiter, is_last=next_char is None,
                                            previous=previous)
            elif char == '#' and next_char == '(':
                part = self._parse_array_query_query_part(i, delimiter, max_end=max_end)
            elif re.match(r'[0-9]', char) and not current:
                part = self._parse_array_index_query_part(i, delimiter, in_multipaths=in_multipaths)
            elif char == '{':
                part = self._parse_object_multipaths_query_part(i, delimiter, max_end=max_end)
                require_delimiter = True
            elif char == '[':
                part = self._parse_array_multipaths_query_part(i, delimiter, max_end=max_end)
                require_delimiter = True
            elif char == '!':
                part = self._parse_literal_query_part(i, delimiter, max_end=max_end, in_multipaths=in_multipaths)
            elif in_multipaths and char == ',':
                i -= 1
                break
            elif in_multipaths and require_delimiter:
                raise GJSONInvalidSyntaxError('Missing separator after multipath.', query=self._query, position=i)

            if part:
                part.previous = previous
                parts.append(part)
                previous = part
            else:  # Normal path, no special grammar
                if not current:
                    current_start = i

                current.append(char)
                if char == ESCAPE_CHARACTER:
                    i += 1  # Skip the escaped character
                    if next_char is None:
                        raise GJSONParseError('Escape character at the end of the query.',
                                              query=self._query, position=i)

                    current.append(next_char)

            if part:
                i = part.end + 1
            else:
                i += 1

        if part is None and current:
            part = FieldQueryPart(start=current_start, end=i, part=''.join(current),
                                  delimiter=delimiter, previous=previous, is_last=True)
            parts.append(part)

        return parts

    @staticmethod
    def _is_sequence(obj: Any) -> bool:
        """Check if an object is a sequence but not a string or bytes object.

        Arguments:
            obj: the object to test.

        Returns:
            :py:data:`True` if the object is a sequence but not a string or bytes, :py:data:`False` otherwise.

        """
        return isinstance(obj, Sequence) and not isinstance(obj, (str, bytes))

    def _find_closing_parentheses(self, *, start: int, opening: str, suffix: str = '', max_end: int = 0) -> int:
        """Find the matching parentheses that closes the opening one looking for unbalance of the given character.

        Arguments:
            start: the index of the opening parentheses in the query.
            opening: the opening parentheses to look for imbalances.
            suffix: an optional suffix that can be present after the closing parentheses before reaching a delimiter or
                the end of the query.
            max_end: an optional last position up to where the parentheses can be found.

        Raises:
            gjson.GJSONParseError: if unable to find the closing parentheses or the parentheses are not balanced.

        Returns:
            the position of the closing parentheses if there is no suffix or the one of the last character of the
            suffix if present.

        """
        closing = PARENTHESES_PAIRS[opening]
        opened = 0
        end = -1
        escaped = False
        in_string = False
        query = self._query[start:max_end + 1] if max_end else self._query[start:]

        for i, char in enumerate(query):
            if char == ESCAPE_CHARACTER:
                escaped = True
                continue

            if escaped:
                escaped = False
                continue

            if char == '"':
                if in_string:
                    in_string = False
                else:
                    in_string = True

                continue

            if in_string:
                continue

            if char == opening:
                opened += 1
            elif char == closing:
                if opened:
                    opened -= 1
                    if not opened:
                        end = i
                        break

        if opened or end < 0:
            raise GJSONParseError(f'Unbalanced parentheses `{opening}`, {opened} still opened.',
                                  query=self._query, position=start)

        if suffix and end + len(suffix) < len(query) and query[end + 1:end + len(suffix) + 1] == suffix:
            end += len(suffix)

        if end + 1 < len(query):
            delimiters = list(MULTIPATHS_DELIMITERS) if max_end else list(DELIMITERS)
            if opening == '(' and suffix == '#':  # Nested queries
                delimiters.append(')')

            if (max_end and query[end + 1] not in delimiters) or (not max_end and query[end + 1] not in DELIMITERS):
                raise GJSONParseError('Expected delimiter or end of query after closing parenthesis.',
                                      query=self._query, position=start + end)

        return start + end

    def _parse_modifier_query_part(self, start: int, delimiter: str, max_end: int = 0,
                                   in_multipaths: bool = False) -> ModifierQueryPart:
        """Find the modifier end position in the query starting from a given point.

        Arguments:
            start: the index of the ``@`` symbol that starts a modifier in the query.
            delimiter: the delimiter before the modifier.
            max_end: an optional last position up to where the last character can be found.
            in_multipaths: whether the part to be parsed is inside a multipaths.

        Raises:
            gjson.GJSONParseError: on invalid modifier.

        Returns:
            the modifier query part object.

        """
        end = start
        escaped = False
        delimiters = MULTIPATHS_DELIMITERS if in_multipaths else DELIMITERS
        options: dict[Any, Any] = {}
        query = self._query[start:max_end + 1] if max_end else self._query[start:]
        for i, char in enumerate(query):
            if char == ESCAPE_CHARACTER and not escaped:
                escaped = True
                continue

            if escaped:
                escaped = False
                continue

            if char == ':':
                name = self._query[start + 1:start + i]
                options_len, options = self._parse_modifier_options(start + i + 1)
                end = start + i + options_len
                break

            if char in delimiters:
                end = start + i - 1
                name = self._query[start + 1:start + i]
                break

        else:  # End of query
            end = start + i
            name = self._query[start + 1:start + i + 1]

        name.replace(ESCAPE_CHARACTER, '')
        if not name:
            raise GJSONParseError('Got empty modifier name.', query=self._query, position=start)

        for char in MODIFIER_NAME_RESERVED_CHARS:
            if char in name:
                raise GJSONParseError(f'Invalid modifier name @{name}, the following characters are not allowed: '
                                      f'{MODIFIER_NAME_RESERVED_CHARS}', query=self._query, position=start)

        return ModifierQueryPart(start=start, end=end, part=self._query[start:end + 1], delimiter=delimiter,
                                 name=name, options=options, is_last=False, previous=None)

    def _parse_modifier_options(self, start: int) -> tuple[int, dict[Any, Any]]:
        """Find the modifier options end position in the query starting from a given point.

        Arguments:
            start: the index of the ``:`` symbol that starts a modifier options.

        Raises:
            gjson.GJSONParseError: on invalid modifier options.

        Returns:
            the modifier options last character index in the query and the parsed options.

        """
        if start >= len(self._query):
            raise GJSONParseError('Modifier with options separator `:` without any option.',
                                  query=self._query, position=start)

        if self._query[start] != '{':
            raise GJSONParseError('Expected JSON object `{...}` as modifier options.',
                                  query=self._query, position=start)

        query_parts = re.split(r'(?<!\\)(\.|\|)', self._query[start:])
        options = None
        options_string = ''
        for i in range(0, len(query_parts), 2):
            options_string = ''.join(query_parts[:i + 1])
            try:
                options = json.loads(options_string, strict=False)
                break
            except json.JSONDecodeError:
                pass
        else:
            raise GJSONParseError('Unable to load modifier options.', query=self._query, position=start)

        return len(options_string), options

    def _parse_array_query_query_part(self, start: int, delimiter: str, max_end: int = 0) -> ArrayQueryQueryPart:
        """Parse an array query part starting from the given point.

        Arguments:
            start: the index of the ``#`` symbol that starts a ``#(...)`` or ``#(...)#`` query.
            delimiter: the delimiter before the modifier.
            max_end: an optional last position up to where the closing parentheses can be found.

        Raises:
            gjson.GJSONParseError: on invalid query.

        Returns:
            the array query part object.

        """
        end = self._find_closing_parentheses(start=start, opening='(', suffix='#', max_end=max_end)
        part = self._query[start:end + 1]
        if part[-1] == '#':
            content_end = -2
            first_only = False
        else:
            content_end = -1
            first_only = True

        content = part[2: content_end]
        query_operator = ''
        key = ''
        value: Union[str, ArrayQueryQueryPart] = ''

        pattern = '|'.join(re.escape(op) for op in QUERIES_OPERATORS)
        match = re.search(fr'(?<!\\)({pattern}|\.?#\()', content)  # Negative lookbehind assertion
        if match:
            query_operator = match.group()
            key = content[:match.start()]
            value = content[match.end():].strip()
        else:  # No operator, assume existence match of key
            key = content

        key = key.strip()
        if match and '#(' in query_operator:  # Nested queries
            offset = 1 if query_operator[0] == '.' else 0
            query_operator = ''
            nested_start = start + 2 + match.start() + offset
            value = self._parse_array_query_query_part(nested_start, delimiter, max_end=end + content_end)
            value.first_only = False  # Nested queries first_only is controlled by the most external query

        if not key and not (query_operator and value) and not isinstance(value, ArrayQueryQueryPart):
            raise GJSONParseError('Empty or invalid query.', query=self._query, position=start)

        return ArrayQueryQueryPart(start=start, end=end, part=part, delimiter=delimiter, is_last=False, previous=None,
                                   field=key, operator=query_operator, value=value, first_only=first_only)

    def _parse_array_index_query_part(self, start: int, delimiter: str,
                                      in_multipaths: bool = False) -> Optional[ArrayIndexQueryPart]:
        """Parse an array index query part.

        Arguments:
            start: the index of the start of the path in the query.
            delimiter: the delimiter before the query part.
            in_multipaths: whether the part to be parsed is inside a multipaths.

        Returns:
            the array index query object if the integer path is found, :py:const:`None` otherwise.

        """
        subquery = self._query[start:]
        delimiters = MULTIPATHS_DELIMITERS if in_multipaths else DELIMITERS
        delimiters_match = '|'.join([re.escape(i) for i in delimiters])
        match = re.search(fr'^([1-9][0-9]*|0)({delimiters_match}|$)', subquery)
        if not match:
            return None

        end = start + len(match.groups()[0]) - 1
        part = self._query[start:end + 1]

        return ArrayIndexQueryPart(start=start, end=end, part=part, delimiter=delimiter, is_last=False, previous=None)

    def _parse_object_multipaths_query_part(
            self, start: int, delimiter: str, max_end: int = 0) -> MultipathsObjectQueryPart:
        """Parse a multipaths object query part.

        Arguments:
            start: the index of the start of the path in the query.
            delimiter: the delimiter before the query part.
            max_end: an optional last position up to where the multipaths can extend.

        Returns:
            the multipaths object query part.

        Raises:
            gjson.GJSONParseError: on invalid query.

        """
        end = self._find_closing_parentheses(start=start, opening='{', max_end=max_end)
        part = self._query[start:end + 1]
        parts = []

        def _get_key(current_key: Optional[str], value: Optional[BaseQueryPart]) -> str:
            """Return the current key or the default value if not set. Allow for empty key as valid key.

            Arguments:
                current_key: the current key to evaluate.
                value: the current value from where to extract a key name if missing.

            """
            if current_key is not None:
                return current_key

            if value and isinstance(value, (FieldQueryPart, ArrayIndexQueryPart, ModifierQueryPart)):
                return value.part

            return '_'

        new_item = True
        escaped = False
        key: Optional[str] = None
        key_start = 0
        value_start = 0
        skip_until = 0

        for i, char in enumerate(part[1:-1], start=1):
            if skip_until and i <= skip_until:
                if i == skip_until:
                    skip_until = 0
                    new_item = True

                continue

            if new_item:
                value_start = 0
                if char == '"':
                    key_start = i
                    new_item = False
                    continue

                if char != ',':
                    value_start = i
                    new_item = False

            if key_start:
                if char == ESCAPE_CHARACTER and not escaped:
                    escaped = True
                    continue

                if escaped:
                    escaped = False
                    continue

                if char == '"':
                    try:
                        key = json.loads(part[key_start:i + 1], strict=False)
                    except json.JSONDecodeError as ex:
                        raise GJSONParseError(f'Failed to parse multipaths key {part[key_start:i + 1]}.',
                                              query=self._query, position=key_start) from ex
                    key_start = 0
                    continue

            if key is not None and not key_start and not value_start:
                if char == ':':
                    value_start = i + 1
                    continue

                raise GJSONParseError(f'Expected colon after multipaths item with key "{key}".',
                                      query=self._query, position=i)

            if value_start:
                try:
                    values = self._parse(
                        start=start + value_start,
                        end=end - 1,
                        max_end=max_end - 1 if max_end else end - 1,
                        delimiter=delimiter,
                        in_multipaths=True)
                except GJSONInvalidSyntaxError:
                    raise
                except GJSONParseError:  # In multipaths, paths that fails are silently suppressed
                    values = []

                if values:
                    parts.append(MultipathsItem(key=_get_key(key, values[-1]), values=values))
                    skip_until = values[-1].end - start + 1
                else:
                    skip_until = end - start

                new_item = True
                key = None
                key_start = 0
                value_start = 0
                continue

        return MultipathsObjectQueryPart(start=start, end=end, part=part, delimiter=delimiter, previous=None,
                                         is_last=False, parts=parts)

    def _parse_array_multipaths_query_part(
            self, start: int, delimiter: str, max_end: int = 0) -> MultipathsArrayQueryPart:
        """Parse a multipaths object query part.

        Arguments:
            start: the index of the start of the path in the query.
            delimiter: the delimiter before the query part.
            max_end: an optional last position up to where the multipaths can extend.

        Returns:
            the multipaths array query part.

        Raises:
            gjson.GJSONParseError: on invalid query.

        """
        end = self._find_closing_parentheses(start=start, opening='[', max_end=max_end)
        part = self._query[start:end + 1]
        parts = []
        skip_until = 0

        for i, _ in enumerate(part[1:-1], start=1):
            if skip_until and i <= skip_until:
                if i == skip_until:
                    skip_until = 0

                continue

            try:
                values = self._parse(
                    start=start + i,
                    end=end - 1,
                    max_end=max_end - 1 if max_end else end - 1,
                    delimiter=delimiter,
                    in_multipaths=True)
            except GJSONInvalidSyntaxError:
                raise
            except GJSONParseError:  # In multipaths, paths that fails are silently suppressed
                values = []

            if values:
                parts.append(values)
                skip_until = values[-1].end - start + 1
            else:
                skip_until = end - start

        return MultipathsArrayQueryPart(start=start, end=end, part=part, delimiter=delimiter, previous=None,
                                        is_last=False, parts=parts)

    def _parse_literal_query_part(self, start: int, delimiter: str, max_end: int = 0,
                                  in_multipaths: bool = False) -> LiteralQueryPart:
        """Parse a literal query part.

        Arguments:
            start: the index of the start of the path in the query.
            delimiter: the delimiter before the query part.
            max_end: an optional last position up to where the multipaths can extend.
            in_multipaths: whether the part to be parsed is inside a multipaths.

        Returns:
            the literal query part.

        Raises:
            gjson.GJSONParseError: on invalid query.

        """
        end = -1
        begin = self._query[start + 1:start + 2]
        if begin in ('{', '['):
            end = self._find_closing_parentheses(start=start + 1, opening=begin, max_end=max_end)

        elif begin == '"':
            query = self._query[start + 2:max_end + 1] if max_end else self._query[start + 2:]
            match = re.search(r'(?<!\\)(")', query)  # Negative lookbehind assertion
            if match is None or match.end() == -1:
                raise GJSONParseError('Unable to find end of literal string.',
                                      query=self._query, position=start + 2)

            # match.end() returns the next position after the last matched character
            end = start + 1 + match.end()

        else:
            query = self._query[start + 1:max_end + 1] if max_end else self._query[start + 1:]
            if match := re.match(r'(true|false|null|NaN|(-)?Infinity)', query):
                # Includes also Infinite and NaN values:
                # https://docs.python.org/3/library/json.html#infinite-and-nan-number-values
                offset = 0
            elif match := re.match(r'-?(0|[1-9][0-9]*)(.[0-9]+)?((e|E)(\+|-|)[0-9]+)?', query):
                offset = 0  # JSON number
            else:  # Catch until the first delimiter or end of string
                delimiters = MULTIPATHS_DELIMITERS if in_multipaths else DELIMITERS
                pattern = '|'.join(re.escape(delimiter) for delimiter in delimiters)
                match = re.search(fr'(?<!\\)({pattern}|$)', query)  # Negative lookbehind assertion
                offset = 1 if match and match.group() else 0

                if match is None or match.end() == -1:  # pragma: nocover the above regex always matches
                    raise GJSONParseError('Invalid JSON literal.', query=self._query, position=start + 1)

            end = start + match.end() - offset  # match.end() gives the next position after the last matched character

        # Allow for empty literals '!' at this point to be able to handle them differently while parsing the parts
        # based if it's in a multipaths or after a query.
        part = self._query[start:end + 1]
        return LiteralQueryPart(start=start, end=end, part=part, delimiter=delimiter, previous=None, is_last=False)

    def _parse_part(self, part: BaseQueryPart, obj: Any, in_multipaths: bool = False) -> Any:
        """Parse the given part of the full query.

        Arguments:
            part: the query part as already parsed.
            obj: the current object.
            in_multipaths: whether the part to be parsed is inside a multipaths.

        Raises:
            gjson.GJSONParseError: on invalid query.

        Returns:
            the result of the query.

        """
        in_hash = False
        in_query_all = False
        ret: Any

        if isinstance(obj, NoResult):
            return obj

        if isinstance(part, ArrayLenghtQueryPart):
            in_hash = True
            if part.is_last:
                if part.delimiter == DOT_DELIMITER and (self._after_hash or self._after_query_all):
                    ret = []
                elif part.delimiter == PIPE_DELIMITER and isinstance(part.previous, ArrayLenghtQueryPart):
                    raise GJSONParseError('The pipe delimiter cannot immediately follow the # element.',
                                          query=self._query, position=part.start)
                elif self._is_sequence(obj):
                    ret = len(obj)
                else:
                    raise GJSONParseError('Expected a sequence like object for query part # at the end of the query, '
                                          f'got {type(obj)}.', query=self._query, position=part.start)
            else:
                ret = obj

        elif isinstance(part, ArrayQueryQueryPart):
            if not self._is_sequence(obj):
                raise GJSONParseError(f'Queries are supported only for sequence like objects, got {type(obj)}.',
                                      query=self._query, position=part.start)

            in_query_all = not part.first_only
            ret = self._parse_query(part, obj)

        elif isinstance(part, ModifierQueryPart):
            ret = self._apply_modifier(part, obj)

        elif isinstance(part, ArrayIndexQueryPart):
            if isinstance(obj, Mapping):  # Integer object keys not supported by JSON
                if not in_multipaths and part.part not in obj:
                    raise GJSONParseError(f'Mapping object does not have key `{part}`.',
                                          query=self._query, position=part.start)
                ret = obj.get(part.part, NoResult())
            elif self._is_sequence(obj):
                if (self._after_hash or self._after_query_all) and part.delimiter == DOT_DELIMITER:
                    # Skip non mapping items and items without the given key
                    ret = [i[part.part] for i in obj if isinstance(i, Mapping) and part.part in i]
                elif (self._after_hash and part.delimiter == PIPE_DELIMITER
                        and isinstance(part.previous, ArrayLenghtQueryPart)):
                    raise GJSONParseError('Integer query part after a pipe delimiter on an sequence like object.',
                                          query=self._query, position=part.start)
                else:
                    num = len(obj)
                    if part.index >= num:
                        raise GJSONParseError(f'Index `{part}` out of range for sequence object with {num} items in '
                                              'query.', query=self._query, position=part.start)
                    ret = obj[part.index]
            else:
                raise GJSONParseError(f'Integer query part on unsupported object type {type(obj)}, expected a mapping '
                                      'or sequence like object.', query=self._query, position=part.start)

        elif isinstance(part, FieldQueryPart):
            if re.search(r'(?<!\\)(\?|\*)', part.part):  # Wildcards
                if not isinstance(obj, Mapping):
                    raise GJSONParseError(f'Wildcard matching key `{part}` requires a mapping object, got {type(obj)} '
                                          'instead.', query=self._query, position=part.start)

                input_parts = re.split(r'(?<!\\)(\?|\*)', part.part)
                pattern_parts = ['^']
                for input_part in input_parts:
                    if not input_part:
                        continue
                    if input_part == '*':
                        if pattern_parts[-1] != '.*':  # Squash all consecutive * to avoid re.match() performance issue
                            pattern_parts.append('.*')
                    elif input_part == '?':
                        pattern_parts.append('.')
                    else:
                        pattern_parts.append(re.escape(re.sub(r'\\(\*|\?)', r'\1', input_part)))
                pattern_parts.append('$')
                pattern = ''.join(pattern_parts)

                for key in obj.keys():
                    if re.match(pattern, key):
                        ret = obj[key]
                        break
                else:
                    raise GJSONParseError(f'No key matching pattern with wildcard `{part}`.',
                                          query=self._query, position=part.start)

            else:
                key = part.part.replace(ESCAPE_CHARACTER, '')
                failed = False
                if not self._after_hash and isinstance(obj, Mapping):
                    if not in_multipaths and key not in obj:
                        raise GJSONParseError(f'Mapping object does not have key `{key}`.',
                                              query=self._query, position=part.start)
                    ret = obj.get(key, NoResult())
                elif (self._after_hash or self._after_query_all) and part.delimiter == DOT_DELIMITER:
                    if self._is_sequence(obj):
                        # Skip non mapping items and items without the given key
                        ret = [i[key] for i in obj if isinstance(i, Mapping) and key in i]
                    elif in_multipaths and isinstance(obj, Mapping):
                        ret = obj.get(key, NoResult())
                    elif in_multipaths:
                        ret = NoResult()
                    else:
                        failed = True
                else:
                    failed = True

                if failed:
                    raise GJSONParseError(f'Invalid or unsupported query part `{key}`.',
                                          query=self._query, position=part.start)

        elif isinstance(part, MultipathsObjectQueryPart):
            if ((self._after_hash or self._after_query_all) and part.delimiter == DOT_DELIMITER
                    and self._is_sequence(obj)):
                ret = []
                for i in obj:
                    obj_item = {}
                    for obj_part in part.parts:
                        obj_ret = i
                        for obj_value in obj_part.values:
                            obj_ret = self._parse_part(obj_value, obj_ret, in_multipaths=True)

                        if not isinstance(obj_ret, NoResult):
                            obj_item[obj_part.key] = obj_ret

                    ret.append(obj_item)
            else:
                ret = {}
                for obj_part in part.parts:
                    obj_ret = obj
                    for obj_value in obj_part.values:
                        obj_ret = self._parse_part(obj_value, obj_ret, in_multipaths=True)

                    if not isinstance(obj_ret, NoResult):
                        ret[obj_part.key] = obj_ret

        elif isinstance(part, MultipathsArrayQueryPart):
            if ((self._after_hash or self._after_query_all) and part.delimiter == DOT_DELIMITER
                    and self._is_sequence(obj)):
                ret = []
                for i in obj:
                    array_item = []
                    for array_part in part.parts:
                        array_ret = i
                        for array_value in array_part:
                            array_ret = self._parse_part(array_value, array_ret, in_multipaths=True)

                        if not isinstance(array_ret, NoResult):
                            array_item.append(array_ret)

                    ret.append(array_item)
            else:
                ret = []
                for array_part in part.parts:
                    array_ret = obj
                    for array_value in array_part:
                        array_ret = self._parse_part(array_value, array_ret, in_multipaths=True)

                    if not isinstance(array_ret, NoResult):
                        ret.append(array_ret)

        elif isinstance(part, LiteralQueryPart):
            try:
                new_obj = json.loads(part.part[1:], strict=False)
                json_error = ''
            except json.JSONDecodeError as ex:
                json_error = str(ex)
                new_obj = NoResult()

            ret = new_obj
            if (self._after_hash or self._after_query_all) and self._is_sequence(obj):
                if part.delimiter == DOT_DELIMITER:
                    if isinstance(new_obj, NoResult):
                        ret = []
                    else:
                        ret = [new_obj for _ in obj]
                elif part.delimiter == PIPE_DELIMITER:
                    ret = new_obj
            else:
                if part.delimiter == DOT_DELIMITER and not isinstance(new_obj, NoResult):
                    json_error = 'literal afer a dot delimiter.'
                    ret = NoResult()
                elif part.delimiter == PIPE_DELIMITER:
                    ret = new_obj

            if not in_multipaths and isinstance(ret, NoResult):
                raise GJSONParseError(
                    f'Unable to load literal JSON: {json_error}', query=self._query, position=part.start)

        if in_hash:
            self._after_hash = True
        if in_query_all:
            self._after_query_all = True

        return ret

    def _evaluate_query_return_value(self, query: ArrayQueryQueryPart, obj: Any) -> Any:
        """Evaluate the return value of an inline query #(...) / #(...)# depending on first match or all matches.

        Arguments:
            query: the query part.
            obj: the current object.

        Raises:
            gjson.GJSONParseError: if the query is for the first element and there are no matching items.

        Returns:
            the result of the query.

        """
        if query.first_only:
            if obj:
                return obj[0]

            raise GJSONParseError('Query for first element does not match anything.',
                                  query=self._query, position=query.start)

        return obj

    def _parse_query(self, query: ArrayQueryQueryPart, obj: Any) -> Any:
        """Parse an inline query #(...) / #(...)#.

        Arguments:
            query: the query part.
            obj: the current object.

        Raises:
            gjson.GJSONParseError: on invalid query.

        Returns:
            the result of the query.

        """
        if isinstance(query.value, ArrayQueryQueryPart):
            ret = []
            for i in obj:
                nested_obj = None
                if query.field:
                    if isinstance(i, Mapping) and query.field in i:
                        nested_obj = i[query.field]
                elif self._is_sequence(i):
                    nested_obj = i

                if nested_obj is not None and self._parse_query(query.value, nested_obj):
                    ret.append(i)

            return self._evaluate_query_return_value(query, ret)

        if not query.operator:
            return self._evaluate_query_return_value(query, [i for i in obj if query.field in i])

        key = query.field.replace('\\', '')
        try:
            value = json.loads(query.value, strict=False)
        except json.JSONDecodeError as ex:
            position = query.start + len(query.field) + len(query.operator)
            raise GJSONParseError(f'Invalid value `{query.value}` for the query key `{key}`.',
                                  query=self._query, position=position) from ex

        if not key and query.first_only and obj and isinstance(obj[0], Mapping):
            raise GJSONParseError('Query on mapping like objects require a key before the operator.',
                                  query=self._query, position=query.start)

        oper: Callable[[Any, Any], bool]
        if query.operator == '==~':
            if value not in (True, False):
                if query.first_only:
                    raise GJSONParseError(f'Queries ==~ operator requires a boolean value, got {type(value)} instead: '
                                          f'`{value}`.', query=self._query, position=query.start + len(query.field))

                return []

            def truthy_op(obj_a: Any, obj_b: bool) -> bool:
                truthy = operator.truth(obj_a)
                if obj_b:
                    return truthy
                return not truthy

            oper = truthy_op
        elif query.operator in ('==', '='):
            oper = operator.eq
        elif query.operator == '!=':
            oper = operator.ne
        elif query.operator == '<':
            oper = operator.lt
        elif query.operator == '<=':
            oper = operator.le
        elif query.operator == '>':
            oper = operator.gt
        elif query.operator == '>=':
            oper = operator.ge
        elif query.operator in ('%', '!%'):
            value = str(value).replace('*', '.*').replace('?', '.')
            value = f'^{value}$'
            if query.operator == '%':
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

        try:
            if key:
                if query.operator == '==~':  # Consider missing keys as falsy according to GJSON docs.
                    ret = [i for i in obj if oper(i.get(key), value)]
                else:
                    ret = [i for i in obj if key in i and oper(i[key], value)]
            else:  # Query on an array of non-objects, match them directly
                ret = [i for i in obj if oper(i, value)]
        except TypeError:
            ret = []

        return self._evaluate_query_return_value(query, ret)

    def _apply_modifier(self, modifier: ModifierQueryPart, obj: Any) -> Any:
        """Apply a modifier.

        Arguments:
            part: the modifier query part to parse.
            obj: the current object before applying the modifier.

        Raises:
            gjson.GJSONError: when the modifier raises an exception.
            gjson.GJSONParseError: on unknown modifier.

        Returns:
            the object modifier according to the modifier.

        """
        try:
            modifier_func = getattr(self, f'_apply_modifier_{modifier.name}')
        except AttributeError:
            modifier_func = self._custom_modifiers.get(modifier.name)
            if modifier_func is None:
                raise GJSONParseError(f'Unknown modifier @{modifier.name}.',
                                      query=self._query, position=modifier.start) from None

        try:
            return modifier_func(modifier.options, obj, last=modifier.is_last)
        except GJSONError:
            raise
        except Exception as ex:
            raise GJSONError(f'Modifier @{modifier.name} raised an exception.') from ex

    def _apply_modifier_reverse(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
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
        if self._is_sequence(obj):
            return obj[::-1]

        return obj

    def _apply_modifier_keys(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @keys modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to get the keys from.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object does not have a keys() method.

        Returns:
            the current object keys as list.

        """
        del last  # for pylint, unused argument
        try:
            return list(obj.keys())
        except AttributeError as ex:
            raise GJSONError('The current object does not have a keys() method.') from ex

    def _apply_modifier_values(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @values modifier.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to get the values from.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object does not have a values() method.

        Returns:
            the current object values as list.

        """
        del last  # for pylint, unused argument
        try:
            return list(obj.values())
        except AttributeError as ex:
            raise GJSONError('The current object does not have a values() method.') from ex

    def _apply_modifier_ugly(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @ugly modifier to condense the output.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to uglyfy.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        self._dump_params['separators'] = (',', ':')
        self._dump_params['indent'] = None
        return obj

    def _apply_modifier_pretty(self, options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @pretty modifier to pretty-print the output.

        Arguments:
            options: the eventual options for the modifier.
            obj: the current object to prettyfy.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        self._dump_params['indent'] = options.get('indent', 2)
        self._dump_params['sort_keys'] = options.get('sortKeys', False)
        self._dump_params['prefix'] = options.get('prefix', '')
        return obj

    def _apply_modifier_ascii(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @ascii modifier to have all non-ASCII characters escaped when dumping the object.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to sort.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        self._dump_params['ensure_ascii'] = True
        return obj

    def _apply_modifier_sort(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @sort modifier, sorts mapping and sequences.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current object to sort.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object is not sortable.

        Returns:
            the sorted object.

        """
        del last  # for pylint, unused argument
        if isinstance(obj, Mapping):
            return {k: obj[k] for k in sorted(obj.keys())}
        if self._is_sequence(obj):
            return sorted(obj)

        raise GJSONError(f'@sort modifier not supported for object of type {type(obj)}. '
                         'Expected a mapping or sequence like object.')

    def _apply_modifier_valid(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @valid modifier, checking that the current object can be converted to JSON.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element to validate.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object cannot be converted to JSON.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        try:
            json.dumps(obj, **self._dump_params)
        except Exception as ex:
            raise GJSONError('The current object cannot be converted to JSON.') from ex

        return obj

    def _apply_modifier_this(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @this modifier, that returns the current object.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element to return.
            last: whether this is the final part of the query.

        Returns:
            the current object, unmodified.

        """
        del last  # for pylint, unused argument
        return obj

    def _apply_modifier_fromstr(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @fromstr modifier, converting a string to JSON, if valid.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element from where to extract the JSON.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object cannot be converted to JSON.

        Returns:
            the parsed JSON.

        """
        del last  # for pylint, unused argument
        if not isinstance(obj, (str, bytes)):
            raise GJSONError(f'Modifier @fromstr got object of type {type(obj)} as input, expected string or bytes.')

        try:
            return json.loads(obj, strict=False)
        except Exception as ex:
            raise GJSONError('The current @fromstr input object cannot be converted to JSON.') from ex

    def _apply_modifier_tostr(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @tostr modifier, converting the current object to a JSON-encoded string, if valid.

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element from where to extract the JSON.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object cannot be converted to a JSON-encoded string.

        Returns:
            the JSON-encoded string.

        """
        del last  # for pylint, unused argument
        try:
            return json.dumps(obj, ensure_ascii=False)
        except Exception as ex:
            raise GJSONError('The current object cannot be converted to a JSON-encoded string for @tostr.') from ex

    def _apply_modifier_group(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @group modifier, that groups a dictionary of lists in a list of dictionaries.

        Example input::

            {"id": ["123", "456", "789"], "val": [2, 1]}

        Example output::

            [{"id": "123", "val": 2}, {"id": "456", "val": 1}, {"id": "789"}]

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element to group.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object is not a dictionary.

        Returns:
            a list with the grouped objects or an empty list if the input has no lists as values.

        """
        del last  # for pylint, unused argument
        if not isinstance(obj, Mapping):
            raise GJSONError(f'Modifier @group got object of type {type(obj)} as input, expected dictionary.')

        # Skip all values that aren't lists:
        obj = {k: v for k, v in obj.items() if self._is_sequence(v)}
        # Fill missing values with NoResult to remove them afterwards
        obj = [dict(zip_longest(obj.keys(), values)) for values in zip_longest(*obj.values(), fillvalue=NoResult())]
        # Skip keys with value NoResult in each dictionary
        return [{k: v for k, v in i.items() if not isinstance(v, NoResult)} for i in obj]

    def _apply_modifier_join(self, _options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @join modifier, that joins a list of dictionaries into a single dictionary.

        Items in the sequence that are not dictionaries are skipped.
        Differently from GJSON there is no support for duplicated keys as the can't exist in Python dictionaries.
        Hence this modifier doesn't accept any option.

        Example input::

            [{"first": "Tom", "age": 37}, {"age": 41}]

        Example output::

            {"first": "Tom", "age":41}

        Arguments:
            options: the eventual options for the modifier, currently unused.
            obj: the current element to join.
            last: whether this is the final part of the query.

        Returns:
            the object untouched if the object is not a sequence, a dictionary with joined objects otherwise.

        """
        del last  # for pylint, unused argument
        if not self._is_sequence(obj):
            return obj

        ret: dict[Any, Any] = {}
        for item in obj:
            if isinstance(item, Mapping):
                ret.update(item)

        return ret

    def _apply_modifier_top_n(self, options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @top_n modifier to find the most common values of a given field.

        Arguments:
            options: the eventual modifier options. If not specified all items are returned. If specified it must
                contain a 'n' key with the number of top N to return.
            obj: the current object to extract the N most common items.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object is not a sequence.

        Returns:
            dict: a dictionary of unique items as keys and the count as value.

        """
        del last  # for pylint, unused argument
        if not self._is_sequence(obj):
            raise GJSONError(f'@top_n modifier not supported for object of type {type(obj)}. '
                             'Expected a sequence like object.')

        return dict(Counter(obj).most_common(options.get('n')))

    def _apply_modifier_sum_n(self, options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @sum_n modifier that groups the values of a given key while summing the values of another key.

        The key used to sum must have numeric values.

        Arguments:
            options: the modifier options. It must contain a 'group' key with the name of the field to use to group the
                items as value and a 'sum' key with the name of the field to use to sum the values for each unique
                grouped identifier. If a 'n' key is also provided, only the top N results are returned. If not
                specified all items are returned.
            obj: the current object to group and sum the top N values.
            last: whether this is the final part of the query.

        Raises:
            gjson.GJSONError: if the current object is not a sequence.

        Returns:
            dict: a dictionary of unique items as keys and the sum as value.

        """
        del last  # for pylint, unused argument
        if not self._is_sequence(obj):
            raise GJSONError(f'@sum_n modifier not supported for object of type {type(obj)}. '
                             'Expected a sequence like object.')

        results: Counter[Any] = Counter()
        for item in obj:
            results[item[options['group']]] += item[options['sum']]
        return dict(results.most_common(options.get('n')))

    def _apply_modifier_flatten(self, options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """Apply the @flatten modifier.

        Arguments:
            options: the eventual modifier options.
            obj: the current object to flatten.
            last: whether this is the final part of the query.

        Returns:
            the modified object.

        """
        del last  # for pylint, unused argument
        if not self._is_sequence(obj):
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
            if self._is_sequence(elem):
                if deep:
                    yield from self._flatten_sequence(elem, deep=deep)
                else:
                    yield from elem
            else:
                yield elem
