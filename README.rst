Introduction
============

gjson-py is a Python package that provides a simple way to filter and extract data from JSON-like objects or JSON
files, using the `GJSON`_ syntax.

It is, compatibly with the language differences and with some limitation, the Python equivalent of the Go
`GJSON`_ package.
The main difference from GJSON is that gjson-py doesn't work directly with JSON strings but instead with
JSON-like Python objects, that can either be the resulting object when calling ``json.load()`` or ``json.loads()``,
or any Python object that is JSON-serializable.

A detailed list of the GJSON features supported by gjson-py is provided below.

Installation
============

gjson-py is available on the `Python Package Index`_ (PyPI) and can be easily installed with::

    pip install gjson

How to use the library
======================

gjson-py provides different ways to perform queries on JSON-like objects.

``gjson.get()``
---------------

A quick accessor to GJSON functionalities exposed for simplicity of use. Particularly useful to perform a single
query on a given object::

    >>> import gjson
    >>> data = {'name': {'first': 'Tom', 'last': 'Anderson'}, 'age': 37}
    >>> gjson.get(data, 'name.first')
    'Tom'

It's also possible to make it return a JSON-encoded string and decide on failure if it should raise an exception
or return `None`. See the full API documentation for more details.

``GJSON`` class
---------------

The ``GJSON`` class provides full access to the gjson-py API allowing to perform multiple queries on the same object::

    >>> import gjson
    >>> data = {'name': {'first': 'Tom', 'last': 'Anderson'}, 'age': 37}
    >>> source = gjson.GJSON(data)
    >>> source.get('name.first')
    'Tom'
    >>> str(source)
    '{"name": {"first": "Tom", "last": "Anderson"}, "age": 37}'
    >>> source.getj('name.first')
    '"Tom"'
    >>> name = source.get_gjson('name')
    >>> name.get('first')
    'Tom'
    >>> name
    <gjson.GJSON object at 0x102735b20>

See the full API documentation for more details.

Query syntax
============

For the generic query syntax refer to the original `GJSON Path Syntax`_ documentation.

Supported GJSON features
------------------------

This is the list of GJSON features and how they are supported by gjson-py:


+------------------------+------------------------+-----------------------------------------------------+
| GJSON feature          | Supported by gjson-py  | Notes                                               |
+========================+========================+=====================================================+
| `Path Structure`_      | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Basic`_               | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Wildcards`_           | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Escape Character`_    | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Arrays`_              | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Queries`_             | PARTIALLY              | Subqueries and the tilde operator are not supported |
+------------------------+------------------------+-----------------------------------------------------+
| `Dot vs Pipe`_         | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Modifiers`_           | PARTIALLY              | See the table below                                 |
+------------------------+------------------------+-----------------------------------------------------+
| `Modifier arguments`_  | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Custom modifier`_     | NO                     |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Multipaths`_          | NO                     |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Literals`_            | NO                     |                                                     |
+------------------------+------------------------+-----------------------------------------------------+

This is the list of GJSON modifiers and how they are supported by gjson-py:

+----------------+-----------------------+-----------------------------------------+
| GJSON Modifier | Supported by gjson-py | Notes                                   |
+----------------+-----------------------+-----------------------------------------+
| ``@reverse``   | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@ugly``      | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@pretty``    | PARTIALLY             | The ``width`` argument is not supported |
+----------------+-----------------------+-----------------------------------------+
| ``@this``      | NO                    |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@valid``     | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@flatten``   | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@join``      | NO                    |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@keys``      | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@values``    | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@tostr``     | NO                    |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@fromstr``   | NO                    |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@group``     | NO                    |                                         |
+----------------+-----------------------+-----------------------------------------+

.. _`GJSON`: https://github.com/tidwall/gjson
.. _`Python Package Index`: https://pypi.org/project/wikimedia-spicerack/
.. _`GJSON Path Syntax`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md

.. _`Path Structure`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#path-structure
.. _`Basic`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#basic
.. _`Wildcards`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#wildcards
.. _`Escape Character`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#escape-character
.. _`Arrays`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#arrays
.. _`Queries`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#queries
.. _`Dot vs Pipe`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#dot-vs-pipe
.. _`Modifiers`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#modifiers
.. _`Modifier arguments`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#modifiers
.. _`Custom modifier`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#modifiers
.. _`Multipaths`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#multipaths
.. _`Literals`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#literals
