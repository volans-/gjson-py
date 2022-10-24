"""gjson custom exceptions module."""
from typing import Any


class GJSONError(Exception):
    """Raised by the gjson module on error while performing queries or converting to JSON."""


class GJSONParseError(GJSONError):
    """Raised when there is an error parsing the query string, with nicer representation of the error."""

    def __init__(self, *args: Any, query: str, position: int):
        """Initialize the exception with the additional data of the query part.

        Arguments:
            *args: all positional arguments like any regular exception.
            query: the full query that generated the parse error.
            position: the position in the query string where the parse error occurred.

        """
        super().__init__(*args)
        self.query = query
        self.position = position

    def __str__(self) -> str:
        """Return a custom representation of the error.

        Returns:
            the whole query string with a clear indication on where the error occurred.

        """
        default = super().__str__()
        line = '-' * (self.position + 7)  # 7 is for the lenght of 'Query: '
        return f'{default}\nQuery: {self.query}\n{line}^'
