"""GJSON module."""
import json
import re
from typing import Any

from pkg_resources import DistributionNotFound, get_distribution

from gjson._gjson import GJSONObj, MODIFIER_NAME_RESERVED_CHARS
from gjson._protocols import ModifierProtocol
from gjson.exceptions import GJSONError, GJSONParseError


# Explicit export of modules for the import * syntax, custom order to force the documentation order
__all__ = ['get', 'GJSON', 'GJSONError', 'GJSONParseError', 'ModifierProtocol', 'GJSONObj', '__version__']


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
        self._custom_modifiers: dict[str, ModifierProtocol] = {}

    def __str__(self) -> str:
        """Return the current object as a JSON-encoded string.

        Examples:
            Converting to string a :py:class:`gjson.GJSON` object returns it as a JSON-encoded string::

                >>> str(gjson_obj)
                '{"items": [{"name": "a", "size": 1}, {"name": "b", "size": 2}]}'

        Returns:
            the JSON-encoded string representing the instantiated object.

        """
        return json.dumps(self._obj, ensure_ascii=False)

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
            return GJSONObj(self._obj, query, custom_modifiers=self._custom_modifiers).get()
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
            return str(GJSONObj(self._obj, query, custom_modifiers=self._custom_modifiers))
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

    def register_modifier(self, name: str, func: ModifierProtocol) -> None:
        """Register a custom modifier.

        Examples:
            Register a custom modifier that sums all the numbers in a list:

                >>> def custom_sum(options, obj, *, last):
                ...     # insert sanity checks code here
                ...     return sum(obj)
                ...
                >>> gjson_obj.register_modifier('sum', custom_sum)
                >>> gjson_obj.get('items.#.size.@sum')
                3

        Arguments:
            name: the modifier name. It will be called where ``@name`` is used in the query. If two custom modifiers
                are registered with the same name the last one will be used.
            func: the modifier code in the form of a callable object that adhere to the
                :py:class:`gjson.ModifierProtocol`.

        Raises:
            gjson.GJSONError: if the provided callable doesn't adhere to the :py:class:`gjson.ModifierProtocol`.

        """
        # Escape the ] as they are inside a [...] block
        not_allowed_regex = ''.join(MODIFIER_NAME_RESERVED_CHARS).replace(']', r'\]')
        if re.search(fr'[{not_allowed_regex}]', name):
            not_allowed_string = ', '.join(f'`{i}`' for i in MODIFIER_NAME_RESERVED_CHARS)
            raise GJSONError(f'Unable to register modifier `{name}`, contains at least one not allowed character: '
                             f'{not_allowed_string}')

        if name in GJSONObj.builtin_modifiers():
            raise GJSONError(f'Unable to register a modifier with the same name of the built-in modifier: @{name}.')

        if not isinstance(func, ModifierProtocol):
            raise GJSONError(f'The given func "{func}" for the custom modifier @{name} does not adhere '
                             'to the gjson.ModifierProtocol.')

        self._custom_modifiers[name] = func


try:
    __version__: str = get_distribution('gjson').version
    """str: the version of the current gjson module."""
except DistributionNotFound:  # pragma: no cover - this should never happen during tests
    pass  # package is not installed
