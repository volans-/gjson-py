.. image:: https://github.com/volans-/gjson-py/actions/workflows/run-tox.yaml/badge.svg
   :alt: CI results
   :target: https://github.com/volans-/gjson-py/actions/workflows/run-tox.yaml

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

See also the full `gjson-py documentation`_.

Installation
------------

gjson-py is available on the `Python Package Index`_ (PyPI) and can be easily installed with::

    pip install gjson

How to use the library
----------------------

gjson-py provides different ways to perform queries on JSON-like objects.

``gjson.get()``
^^^^^^^^^^^^^^^

A quick accessor to GJSON functionalities exposed for simplicity of use. Particularly useful to perform a single
query on a given object::

    >>> import gjson
    >>> data = {'name': {'first': 'Tom', 'last': 'Anderson'}, 'age': 37}
    >>> gjson.get(data, 'name.first')
    'Tom'

It's also possible to make it return a JSON-encoded string and decide on failure if it should raise an exception
or return `None`. See the full API documentation for more details.

``GJSON`` class
^^^^^^^^^^^^^^^

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

How to use the CLI
------------------

gjson-py provides also a command line interface (CLI) for ease of use:

.. code-block:: console

    $ echo '{"name": {"first": "Tom", "last": "Anderson"}, "age": 37}' > test.json
    $ cat test.json | gjson 'name.first'  # Read from stdin
    "Tom"
    $ gjson test.json 'age'  # Read from a file
    37
    $ cat test.json | gjson - 'name.first'  # Explicitely read from stdin
    "Tom"

JSON Lines
^^^^^^^^^^

JSON Lines support in the CLI allows for different use cases. All the examples in this section operates on a
``test.json`` file generated with:

.. code-block:: console

    $ echo -e '{"name": "Gilbert", "age": 61}\n{"name": "Alexa", "age": 34}\n{"name": "May", "age": 57}' > test.json

Apply the same query to each line
"""""""""""""""""""""""""""""""""

Using the ``-l/--lines`` CLI argument, for each input line gjson-py applies the query and filters the data according
to it. Lines are read one by one so there is no memory overhead for the processing. It can be used while tailing log
files in JSON format for example.


.. code-block:: console

    $ gjson --lines test.json 'age'
    61
    34
    57
    $ tail -f log.json | gjson --lines 'bytes_sent'  # Dummy example

Encapsulate all lines in an array, then apply the query
"""""""""""""""""""""""""""""""""""""""""""""""""""""""

Using the special query prefix syntax ``..``, as described in GJSON's documentation for `JSON Lines`_, gjson-py will
read all lines from the input and encapsulate them into an array. This approach has of course the memory overhead of
loading the whole input to perform the query.

.. code-block:: console

    $ gjson test.json '..#.name'
    ["Gilbert", "Alexa", "May"]

Filter lines based on their values
""""""""""""""""""""""""""""""""""

Combining the ``-l/--lines`` CLI argument with the special query prefix ``..`` described above, it's possible to filter
input lines based on their values. In this case gjson-py encapsulates each line in an array so that is possible to use
the `Queries`_ GJSON syntax to filter them. As the ecapsulation is performed on each line, there is no memory overhead.
Because technically when a line is filtered is because there was no match on the whole line query, the final exit code,
if any line is filtered, will be ``1``.

.. code-block:: console

    $ gjson --lines test.json '..#(age>40).name'
    "Gilbert"
    "May"

Filter lines and apply query to the result
""""""""""""""""""""""""""""""""""""""""""

Combining the methods above is possible for example to filter/extract data from the lines first and then apply a query
to the aggregated result. The memory overhead in this case is based on the amount of data resulting from the first
filtering/extraction.

.. code-block:: console

    $ gjson --lines test.json 'age' | gjson '..@sort'
    [34, 57, 61]
    $ gjson --lines test.json '..#(age>40).age' | gjson '..@sort'
    [57, 61]

Query syntax
------------

For the generic query syntax refer to the original `GJSON Path Syntax`_ documentation.

Supported GJSON features
^^^^^^^^^^^^^^^^^^^^^^^^

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
| `Queries`_             | PARTIALLY              | Subqueries are not supported [#]_                   |
+------------------------+------------------------+-----------------------------------------------------+
| `Dot vs Pipe`_         | YES                    |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Modifiers`_           | PARTIALLY              | See the table below                                 |
+------------------------+------------------------+-----------------------------------------------------+
| `Modifier arguments`_  | YES                    | Only a JSON object is accepted as argument          |
+------------------------+------------------------+-----------------------------------------------------+
| `Custom modifiers`_    | YES                    | Only a JSON object is accepted as argument          |
+------------------------+------------------------+-----------------------------------------------------+
| `Multipaths`_          | NO                     |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `Literals`_            | NO                     |                                                     |
+------------------------+------------------------+-----------------------------------------------------+
| `JSON Lines`_          | YES                    | CLI support [#]_ [#]_                               |
+------------------------+------------------------+-----------------------------------------------------+

.. [#] The queries matching is based on Python's operator and as such the results might be different than the ones from
   the Go GJSON package. In particular for the ``~`` operator that checks the truthy-ness of objects.
.. [#] Both for applying the same query to each line using the ``-l/--lines`` argument and to automatically encapsulate
   the input lines in a list and apply the query to the list using the ``..`` special query prefix described in
   `JSON Lines`_.
.. [#] Library support is not currently present because gjson-py accepts only Python objects, making it impossible to
   pass JSON Lines directly. The client is free to choose if calling gjson-py for each line or to encapsulate them in
   a list before calling gjson-py.

This is the list of modifiers and how they are supported by gjson-py:

+----------------+-----------------------+-----------------------------------------+
| GJSON Modifier | Supported by gjson-py | Notes                                   |
+----------------+-----------------------+-----------------------------------------+
| ``@reverse``   | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@ugly``      | YES                   |                                         |
+----------------+-----------------------+-----------------------------------------+
| ``@pretty``    | PARTIALLY             | The ``width`` argument is not supported |
+----------------+-----------------------+-----------------------------------------+
| ``@this``      | YES                   |                                         |
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
| ``@sort``      | YES                   | Not present in GJSON                    |
+----------------+-----------------------+-----------------------------------------+

.. _`GJSON`: https://github.com/tidwall/gjson
.. _`Python Package Index`: https://pypi.org/project/gjson/
.. _`GJSON Path Syntax`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md
.. _`gjson-py documentation`: https://volans-.github.io/gjson-py/index.html

.. _`Path Structure`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#path-structure
.. _`Basic`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#basic
.. _`Wildcards`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#wildcards
.. _`Escape Character`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#escape-character
.. _`Arrays`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#arrays
.. _`Queries`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#queries
.. _`Dot vs Pipe`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#dot-vs-pipe
.. _`Modifiers`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#modifiers
.. _`Modifier arguments`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#modifiers
.. _`Custom modifiers`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#custom-modifiers
.. _`Multipaths`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#multipaths
.. _`Literals`: https://github.com/tidwall/gjson/blob/master/SYNTAX.md#literals
.. _`JSON Lines`: https://github.com/tidwall/gjson#json-lines
