"""Typing protocols used by the gjson package."""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ModifierProtocol(Protocol):
    """Callback protocol for the custom modifiers."""

    def __call__(self, options: dict[str, Any], obj: Any, *, last: bool) -> Any:
        """To register a custom modifier a callable that adhere to this protocol must be provided.

        Examples:
            Register a custom modifier that sums all the numbers in a list:

                >>> import gjson
                >>> data = [1, 2, 3, 4, 5]
                >>> def custom_sum(options, obj, *, last):
                ...     # insert sanity checks code here
                ...     return sum(obj)
                ...
                >>> gjson_obj = gjson.GJSON(data)
                >>> gjson_obj.register_modifier('sum', custom_sum)
                >>> gjson_obj.get('@sum')
                15

        Arguments:
            options: a dictionary of options. If no options are present in the query the callable will be called with
                an empty dictionary as options. The modifier can supports any number of options, or none.
            obj: the current object already modifier by any previous parts of the query.
            last: :py:data:`True` if the modifier is the last element in the query or :py:data:`False` otherwise.

        Raises:
            Exception: any exception that might be raised by the callable is catched by gjson and re-raised as a
                :py:class:`gjson.GJSONError` exception to ensure that the normal gjson behaviour is respected according
                to the selected verbosity (CLI) or ``quiet`` parameter (Python library).

        Returns:
            the resulting object after applying the modifier.

        """
