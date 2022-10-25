Release Notes
=============

`v0.2.1`_ (2022-10-25)
^^^^^^^^^^^^^^^^^^^^^^

Bug fixes
"""""""""

* Query parsing: fix modifier options:

  * Fix a bug that was failing to properly get the modifier name when there were options and the modifier was not the
    first path in the query.

`v0.2.0`_ (2022-10-24)
^^^^^^^^^^^^^^^^^^^^^^

New features
""""""""""""

* Query parsing: fully rewrite of the query parser:

  * Until now the parsing was mostly relying on a couple of regular expressions with lookbehind assertions to take
    into account escaped characters. Although they were working fine and also allowed to sensibly speed up the first
    development of gjson-py, they also had two major limitations:

    * Could not work in all corner cases.
    * Prevented the implementation of the GJSON features still missing in gjson-py.

  * The parsing has been completely refactored using a more standard parser approach, that allows to fine-tune the
    parsing much more to cover all corner cases and also enables the development of GJSON features still missing.
  * There shouldn't be any difference for normal queries, but some corner cases might now return a proper error.
  * Introduced a new ``GJSONParseError`` for parser-specific errors, that inherits from GJSONError and also provides
    a graphic way to show where the parsing error occurred. Example output::

      GJSONParseError: Invalid or unsupported query part `invalid`.
      Query: name.last.invalid
      -----------------^

Minor improvements
""""""""""""""""""

* Refactor code splitting it into multiple files:

  * Restructure the gjson code to split it into multiple files for ease of development and maintenance.
  * Keep all the split modules as private except the exceptions one, and re-export everything from the gjson module
    itself, both to keep backward compatibility and also for simplicity of use by the clients.

* Custom modifiers:

  * Prevent to register custom modifiers with names that contains characters that are used by the GJSON grammair,
    raising a GJSONError exception.

Miscellanea
"""""""""""

* README: clarify naming for nested queries, based on feedback from `issue #2`_. Also fix a typo.

`v0.1.0`_ (2022-10-03)
^^^^^^^^^^^^^^^^^^^^^^

Minor improvements
""""""""""""""""""

*  Modifiers: add ``@top_n`` modifier (not present in GJSON):

  * Add a ``@top_n`` modifier that optionally accepts as options the number of top common items to return:
    ``@top_n:{"n": 5}``
  * If no options are provided all items are returned.
  * It requires a list of items as input and returns a dictionary with unique items as keys and the count of them as
    values.

*  Modifiers: add ``@sum_n`` modifier (not present in GJSON):

  * Add a ``@sum_n`` modifier that will work on a sequence of objects, grouping the items with the same value for a
    given grouping key and sum the values of a sum key for each of them.
  * The options are mandatory and must specify the key to use for grouping and the key to use for summing:
    ``{"group": "somekey", "sum": "anotherkey"}``. Optionally specifying the ``n`` parameter to just return the top N
    results based on the summed value: ``{"group": "somekey", "sum": "anotherkey", "n": 5}``
  * It requires a list of objects as input and returns a dictionary with unique items as keys and the sum of their
    values as values.

Bug fixes
"""""""""

* Output: fix unicode handling:

  * Fix the default behaviour ensuring non-ASCII characters are returned as-is.
  * Add a new modifier ``@ascii``, that when set will escape all non-ASCII characters.

* CLI: fix encoding handling:

  * Use the ``surrogateescape`` Python mode when reading the input and back when printing the output to prevent
    failures when parsing the input and reducing the loss of data.

Miscellanea
"""""""""""

* documentation: add mention to Debian packaging and the availability of Debian packages for the project.
* Type hints: use native types when possible. Instead of importing from ``typing`` use directly the native types when
  they support the ``[]`` syntax added in Python 3.9.
* documentation: refactor the modifiers documentation to clearly split the GJSON modifiers supported by gjson-py and
  the additional modifiers specific to gjson-py with more detailed explanation and example usage for the additional
  ones.
* setup.py: mark project as Beta for this ``v0.1.0`` release and add an additional keyword for PyPI indexing.

`v0.0.5`_ (2022-08-05)
^^^^^^^^^^^^^^^^^^^^^^

New features
""""""""""""

* Queries: add support for the tilde operator:

  * When performing queries on arrays, add support for the Go GJSON tilde operator to perform truthy-ness comparison.
  * The comparison is based on Python's definition of truthy-ness, hence the actual results might differ from the ones
    in the Go package.

Minor improvements
""""""""""""""""""

* documentation: add man page for the gjson binary.

`v0.0.4`_ (2022-06-11)
^^^^^^^^^^^^^^^^^^^^^^

New features
""""""""""""

* CLI: improve the JSON Lines support allowing to use the ``-l/--lines`` CLI argument and the special query prefix
  ``..`` syntax together to encapsulate each parsed line in an array to enable filtering using the Queries
  capabilities.

Minor improvements
""""""""""""""""""

* CLI: the input file CLI argument is now optional, defaulting to read from stdin. The equivalent of passing ``-``.
* Modifiers: add support for the upstream Go GJSON modifier ``@this``, that just returns the current object.

Miscellanea
"""""""""""

* Documentation: add a section to with examples on how to use the CLI.
* CLI: add a link at the bottom of the help message of the CLI to the online documentation.

`v0.0.3`_ (2022-06-11)
^^^^^^^^^^^^^^^^^^^^^^

New features
""""""""""""

* Add CLI support for JSON Lines:

  * Add a ``-l/--lines`` CLI argument to specify that the input file/stream is made of one JSON per line.
  * When used, gjson applies the same query to all lines.
  * Based on the verbosity level the failing lines are completely ignored, an error message is printed to stderr or
    the execution is interrupted at the first error printing the full traceback.

* Add CLI support for GJSON JSON Lines queries:

  * Add support for the GJSON queries that encapsulates a JSON Lines input in an array when the query starts with
    ``..`` so that they the data can be queries as if it was an array of objects in the CLI.

* Add support for custom modifiers:

  * Add a ``ModifierProtocol`` to describe the interface that custom modifiers callable need to have.
  * Add a ``register_modifier()`` method in the ``GJSON`` class to register custom modifiers.
  * Allow to pass a dictionary of modifiers to the low-level ``GJSONObj`` class constructor.
  * Add a ``GJSONObj.builtin_modifiers()`` static method that returns a set with the names of the built-in modifiers.
  * Is not possible to register a custom modifier with the same name of a built-in modifier.
  * Clarify in the documentation that only JSON objects are accepted as modifier arguments.

Bug fixes
"""""""""

* Query parsing: when using the queries GJSON syntax ``#(...)`` and ``#(...)#`` fix the return value in case of a key
  matching that doesn't match any element.

* Query parsing fixes/improvements found with the Python fuzzing engine Atheris:

  * If any query parts between delimiters is empty error out with a specific message instead of hitting a generic
    ``IndexError``.
  * When a query has an integer index on a mapping object, in case the element is not present, raise a ``GJSONError``
    instead of a ``KeyError`` one.
  * When the query has a wildcard matching, ensure that it's applied on a mapping object. Fail with a ``GJSONError``
    otherwise.
  * Explicitly catch malformed modifier options and raise a ``GJSONError`` instead.
  * If the last part of the query is a ``#``, check that the object is actually a sequence like object and fail with
    a specific message if not.
  * Ensure all the conditions are valid before attempting to extract the inner element of a sequence like object.
    Ignore both non-mapping like objects inside the sequence or mapping like objects that don't have the specified key.
  * When parsing the query value as JSON catch the eventual decoding error to encapsulate it into a ``GJSONError`` one.
  * When using the queries GJSON syntax ``#(...)`` and ``#(...)#`` accept also an empty query to follow the same
    behaviour of the upstream Go GJSON.
  * When using the queries GJSON syntax ``#(...)`` and ``#(...)#`` follow closely the upstream behaviour of Go GJSON
    for all items queries ``#(..)#`` with regex matching.
  * When using the queries GJSON syntax ``#(...)`` and ``#(...)#`` fix the wildcard matching regular expression when
    using pattern matching.
  * Fix the regex to match keys in presence of wildcards escaping only the non-wildcards and ensuring to not
    double-escaping any already escaped wildcard.
  * When using the queries GJSON syntax ``#(...)`` and ``#(...)#`` ensure any exception raised while comparing
    incompatible objects is catched and raise as a GJSONError.

Miscellanea
"""""""""""

* tests: when matching exception messages always escape the string or use raw strings to avoid false matchings.
* pylint: remove unnecessary comments

`v0.0.2`_ (2022-05-31)
^^^^^^^^^^^^^^^^^^^^^^

Bug fixes
"""""""""

* ``@sort`` modifier: fix the actual sorting.
* tests: ensure that mapping-like objects are compared also in the order of their keys.

Miscellanea
"""""""""""

* GitHub actions: add workflow to run tox.
* GitHub actions: fix branch name for pushes
* documentation: include also the ``@sort`` modifier that is not present in the GJSON project.
* documentation: fix link to PyPI package.
* documentation: add link to the generated docs.
* documentation: fix section hierarchy and build.

`v0.0.1`_ (2022-05-22)
^^^^^^^^^^^^^^^^^^^^^^

* Initial version.

.. _`issue #2`: https://github.com/volans-/gjson-py/issues/2

.. _`v0.0.1`: https://github.com/volans-/gjson-py/releases/tag/v0.0.1
.. _`v0.0.2`: https://github.com/volans-/gjson-py/releases/tag/v0.0.2
.. _`v0.0.3`: https://github.com/volans-/gjson-py/releases/tag/v0.0.3
.. _`v0.0.4`: https://github.com/volans-/gjson-py/releases/tag/v0.0.4
.. _`v0.0.5`: https://github.com/volans-/gjson-py/releases/tag/v0.0.5
.. _`v0.1.0`: https://github.com/volans-/gjson-py/releases/tag/v0.1.0
.. _`v0.2.0`: https://github.com/volans-/gjson-py/releases/tag/v0.2.0
.. _`v0.2.1`: https://github.com/volans-/gjson-py/releases/tag/v0.2.1
