"""GJSON test module."""
# pylint: disable=attribute-defined-outside-init
import argparse
import io
import json
import re

from typing import Mapping

import pytest

import gjson


INPUT_JSON = """
{
    "name": {"first": "Tom", "last": "Anderson"},
    "age":37,
    "children": ["Sara","Alex","Jack"],
    "fav.movie": "Deer Hunter",
    "friends": [
        {"first": "Dale", "last": "Murphy", "age": 44, "nets": ["ig", "fb", "tw"]},
        {"first": "Roger", "last": "Craig", "age": 68, "nets": ["fb", "tw"]},
        {"first": "Jane", "last": "Murphy", "age": 47, "nets": ["ig", "tw"]}
    ]
}
"""
INPUT_OBJECT = json.loads(INPUT_JSON)
INPUT_LIST = json.loads("""
[
    {"first": "Dale"},
    {"first": "Jane"},
    {"last": "Murphy"}
]
""")
INPUT_ESCAPE = json.loads("""
{
    "test": {
        "*":"valZ",
        "*v":"val0",
        "keyv*":"val1",
        "key*v":"val2",
        "keyv?":"val3",
        "key?v":"val4",
        "keyv.":"val5",
        "key.v":"val6",
        "keyk*":{"key?":"val7"}
    }
}
""")
# This json block is poorly formed on purpose.
INPUT_BASIC = json.loads("""
  {"age":100, "name2":{"here":"B\\\\\\"R"},
    "noop":{"what is a wren?":"a bird"},
    "happy":true,"immortal":false,
    "items":[1,2,3,{"tags":[1,2,3],"points":[[1,2],[3,4]]},4,5,6,7],
    "arr":["1",2,"3",{"hello":"world"},"4",5],
    "vals":[1,2,3],"name":{"first":"tom","last":null},
    "created":"2014-05-16T08:28:06.989Z",
    "loggy":{
        "programmers": [
            {
                "firstName": "Brett",
                "lastName": "McLaughlin",
                "email": "aaaa",
                "tag": "good"
            },
            {
                "firstName": "Jason",
                "lastName": "Hunter",
                "email": "bbbb",
                "tag": "bad"
            },
            {
                "firstName": "Elliotte",
                "lastName": "Harold",
                "email": "cccc",
                "tag": "good"
            },
            {
                "firstName": 1002.3,
                "age": 101
            }
        ]
    },
    "lastly":{"end...ing":"soon","yay":"final"}
}
""")
INPUT_LINES = """
{"name": "Gilbert", "age": 61}
{"name": "Alexa", "age": 34}
{"name": "May", "age": 57}
{"name": "Deloise", "age": 44}
"""
INPUT_LINES_WITH_ERRORS = """
{"name": "Gilbert", "age": 61}
{invalid
{invalid
{"name": "Deloise", "age": 44}
"""
INPUT_TRUTHINESS = json.loads("""
{
  "vals": [
    { "a": 1, "b": true },
    { "a": 2, "b": true },
    { "a": 3, "b": false },
    { "a": 4, "b": "0" },
    { "a": 5, "b": 0 },
    { "a": 6, "b": "1" },
    { "a": 7, "b": 1 },
    { "a": 8, "b": "true" },
    { "a": 9, "b": false },
    { "a": 10, "b": null },
    { "a": 11 }
  ]
}
""")


def compare_values(result, expected):
    """Compare results with the expected values ensuring same-order of keys for dictionaries."""
    assert result == expected
    if isinstance(expected, Mapping):
        assert list(result.keys()) == list(expected.keys())


class TestObject:
    """Testing gjson with a basic input object."""

    def setup_method(self):
        """Initialize the test instance."""
        self.object = gjson.GJSON(INPUT_OBJECT)

    @pytest.mark.parametrize('query, expected', (
        # Basic
        ('name.last', 'Anderson'),
        ('name.first', 'Tom'),
        ('age', 37),
        ('children', ['Sara', 'Alex', 'Jack']),
        ('children.0', 'Sara'),
        ('children.1', 'Alex'),
        ('friends.1', {'first': 'Roger', 'last': 'Craig', 'age': 68, 'nets': ['fb', 'tw']}),
        ('friends.1.first', 'Roger'),
        # Wildcards
        ('*.first', 'Tom'),
        ('?a??.first', 'Tom'),
        ('child*.2', 'Jack'),
        ('c?ildren.0', 'Sara'),
        # Escape characters
        (r'fav\.movie', 'Deer Hunter'),
        # Arrays
        ('friends.#', 3),
        ('friends.#.age', [44, 68, 47]),
        ('friends.#.first', ['Dale', 'Roger', 'Jane']),
        # Queries
        ('children.#()', "Sara"),
        ('children.#()#', ["Sara", "Alex", "Jack"]),
        ('friends.#.invalid.#()', []),
        ('friends.#.invalid.#()#', []),
        ('friends.#(last=="Murphy").first', 'Dale'),
        ('friends.#(last=="Murphy")#.first', ['Dale', 'Jane']),
        ('friends.#(=="Murphy")#', []),
        ('friends.#(age>47)#.last', ['Craig']),
        ('friends.#(age>=47)#.last', ['Craig', 'Murphy']),
        ('friends.#(age<47)#.last', ['Murphy']),
        ('friends.#(age<=47)#.last', ['Murphy', 'Murphy']),
        ('friends.#(age==44)#.last', ['Murphy']),
        ('friends.#(age!=44)#.last', ['Craig', 'Murphy']),
        ('friends.#(first%"D*").last', 'Murphy'),
        ('friends.#(first!%"D*").last', 'Craig'),
        ('friends.#(first!%"D???").last', 'Craig'),
        ('friends.#(%0)#', []),
        ('friends.#(>40)#', []),
        ('children.#(!%"*a*")', 'Alex'),
        ('children.#(%"*a*")#', ['Sara', 'Jack']),
        # Nested queries (TODO)
        # ('friends.#(nets.#(=="fb"))#.first', ['Dale', 'Roger']),
        # Tilde in queries (TODO)
        # ('vals.#(b==~true)#.a')
        # Modifiers
        ('children.@reverse', ['Jack', 'Alex', 'Sara']),
        ('children.@reverse.0', 'Jack'),
        ('name.@reverse', {'last': 'Anderson', 'first': 'Tom'}),
        ('age.@reverse', 37),
        ('@keys', ['name', 'age', 'children', 'fav.movie', 'friends']),
        ('name.@values', ['Tom', 'Anderson']),
        ('age.@flatten', 37),
        # Dot vs Pipe
        ('friends.0.first', 'Dale'),
        ('friends|0.first', 'Dale'),
        ('friends.0|first', 'Dale'),
        ('friends|0|first', 'Dale'),
        ('friends|#', 3),
        ('friends.#', 3),
        ('friends.#(last="Murphy")#',
         [{'first': 'Dale', 'last': 'Murphy', 'age': 44, 'nets': ['ig', 'fb', 'tw']},
          {'first': 'Jane', 'last': 'Murphy', 'age': 47, 'nets': ['ig', 'tw']}]),
        ('friends.#(last="Murphy")#.first', ['Dale', 'Jane']),
        ('friends.#(last="Murphy")#.0', []),
        ('friends.#(last="Murphy")#|0', {'first': 'Dale', 'last': 'Murphy', 'age': 44, 'nets': ['ig', 'fb', 'tw']}),
        ('friends.#(last="Murphy")#.#', []),
        ('friends.#(last="Murphy")#|#', 2),
    ))
    def test_get_ok(self, query, expected):
        """It should query the JSON object and return the expected result."""
        compare_values(self.object.get(query), expected)

    @pytest.mark.parametrize('query, error', (
        # Basic
        ('', 'Empty query'),
        ('age.0', "Integer query part on unsupported object type <class 'int'>"),
        ('friends.99', 'Index 99 out of range for sequence object with 3 items in query friends.99'),
        ('name.nonexistent', 'Mapping object does not have key nonexistent for query name.nonexistent'),
        ('name.1', 'Mapping object does not have key 1 for query name.1'),
        ('children.invalid', 'Invalid or unsupported query part "invalid" for query children.invalid.'),
        # Wildcards
        ('x*', 'No key matching pattern with wildcard x*'),
        ('??????????', 'No key matching pattern with wildcard ??????????'),
        ('children.x*', "Wildcard matching key x* in query children.x* requires a mapping object, got <class 'list'>"),
        ('(-?', 'No key matching pattern with wildcard (-?.'),
        # Queries
        ('#', "Expected a sequence like object for query part # at the end of the query, got <class 'dict'>."),
        ('#.invalid', 'Invalid or unsupported query part "invalid" for query #.invalid.'),
        ('friends.#(=="Murphy")', 'Query on mapping like objects require a key before the operator.'),
        ('friends.#(last=={1: 2})', 'Invalid value "{1: 2}" for the query key "last".'),
        ('friends.#(invalid', 'Invalid query part #(invalid. Expected in the format'),
        ('#(first)', 'Queries are supported only for sequence like objects'),
        ('friends.#(last=="invalid")', 'Query part last=="invalid" for first element does not match anything.'),
        ('friends.#(first%"D?")', 'Query part first%"D?" for first element does not match anything.'),
        # Dot vs Pipe
        ('friends.#(last="Murphy")#|first', 'Invalid or unsupported query'),
        # Modifiers
        ('@pretty:', 'Unable to load options for modifier @pretty'),
        ('@pretty:{invalid', 'Unable to load options for modifier @pretty'),
        ('@pretty:["invalid"]',
         "Invalid options for modifier @pretty, expected mapping got <class 'list'>: ['invalid']"),
        ('@invalid', 'Unknown modifier @invalid'),
        ('children.@keys', 'The current object does not have a keys() method.'),
        ('children.@values', 'The current object does not have a values() method.'),
        # JSON Lines
        ('..name', 'Empty query part between two delimiters'),
    ))
    def test_get_raise(self, query, error):
        """It should raise a GJSONError error with the expected message."""
        with pytest.raises(gjson.GJSONError, match=re.escape(error)):
            self.object.get(query)


class TestEscape:
    """Test gjson for all the escape sequences."""

    def setup_method(self):
        """Initialize the test instance."""
        self.escape = gjson.GJSON(INPUT_ESCAPE)

    @pytest.mark.parametrize('query, expected', (
        (r'test.\*', 'valZ'),
        (r'test.\*v', 'val0'),
        (r'test.keyv\*', 'val1'),
        (r'test.key\*v', 'val2'),
        (r'test.keyv\?', 'val3'),
        (r'test.key\?v', 'val4'),
        (r'test.keyv\.', 'val5'),
        (r'test.key\.v', 'val6'),
        (r'test.keyk\*.key\?', 'val7'),
    ))
    def test_get_ok(self, query, expected):
        """It should query the escape test JSON and return the expected result."""
        assert self.escape.get(query, quiet=True) == expected


class TestBasic:
    """Test gjson for basic queries."""

    def setup_method(self):
        """Initialize the test instance."""
        self.basic = gjson.GJSON(INPUT_BASIC)

    @pytest.mark.parametrize('query, expected', (
        ('loggy.programmers.#(age=101).firstName', 1002.3),
        ('loggy.programmers.#(firstName != "Brett").firstName', 'Jason'),
        ('loggy.programmers.#(firstName % "Bre*").email', 'aaaa'),
        ('loggy.programmers.#(firstName !% "Bre*").email', 'bbbb'),
        ('loggy.programmers.#(firstName == "Brett").email', 'aaaa'),
        ('loggy.programmers.#.firstName', ['Brett', 'Jason', 'Elliotte', 1002.3]),
        ('loggy.programmers.#.asd', []),
        ('items.3.tags.#', 3),
        ('items.3.points.1.#', 2),
        ('items.#', 8),
        ('vals.#', 3),
        ('name2.here', r'B\"R'),
        ('arr.#', 6),
        ('arr.3.hello', 'world'),
        ('name.first', 'tom'),
        ('name.last', None),
        ('age', 100),
        ('happy', True),
        ('immortal', False),
        ('noop', {'what is a wren?': 'a bird'}),
    ))
    def test_get_ok(self, query, expected):
        """It should query the basic test JSON and return the expected result."""
        assert self.basic.get(query) == expected


class TestList:
    """Test gjson queries on a list object."""

    def setup_method(self):
        """Initialize the test instance."""
        self.list = gjson.GJSON(INPUT_LIST)

    @pytest.mark.parametrize('query, expected', (
        # Dot vs Pipe
        ('#.first', ['Dale', 'Jane']),
        ('#.first.#', []),
        ('#.first|#', 2),
        ('#.0', []),
        ('#.#', []),
        # Queries
        ('#(first)#', [{'first': 'Dale'}, {'first': 'Jane'}]),
        ('#(first)', {'first': 'Dale'}),
        ('#(last)#', [{'last': 'Murphy'}]),
        ('#(last)', {'last': 'Murphy'}),
    ))
    def test_get_ok(self, query, expected):
        """It should query the list test JSON and return the expected result."""
        assert self.list.get(query, quiet=True) == expected

    @pytest.mark.parametrize('query, error', (
        # Dot vs Pipe
        ('#|first', 'Invalid or unsupported query part "first" for query #|first.'),
        ('#|0', 'Integer query part after a pipe delimiter on an sequence like object.'),
        ('#|#', 'The pipe delimiter cannot immediately follow the # element.'),
    ))
    def test_get_raise(self, query, error):
        """It should raise a GJSONError error with the expected message."""
        with pytest.raises(gjson.GJSONError, match=re.escape(error)):
            self.list.get(query)


class TestFlatten:
    """Test gjson @flatten modifier."""

    def setup_method(self):
        """Initialize the test instance."""
        self.list = gjson.GJSON(json.loads('[1, [2], [3, 4], [5, [6, 7]], [8, [9, [10, 11]]]]'))

    @pytest.mark.parametrize('query, expected', (
        ('@flatten', [1, 2, 3, 4, 5, [6, 7], 8, [9, [10, 11]]]),
        ('@flatten:{"deep":true}', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    ))
    def test_get(self, query, expected):
        """It should correctly flatten the given object."""
        assert self.list.get(query, quiet=True) == expected


class TestTruthiness:
    """Testing gjson with an input object with truthy/falsy objects."""

    def setup_method(self):
        """Initialize the test instance."""
        self.object = gjson.GJSON(INPUT_TRUTHINESS)

    @pytest.mark.parametrize('query, expected', (
        ('vals.#(b==~true).a', 1),
        ('vals.#(b==~true)#.a', [1, 2, 4, 6, 7, 8]),
        ('vals.#(b==~false).a', 3),
        ('vals.#(b==~false)#.a', [3, 5, 9, 10, 11]),
        ('vals.#(b==~"invalid")#', []),
    ))
    def test_get_ok(self, query, expected):
        """It should query the JSON object and return the expected result."""
        compare_values(self.object.get(query), expected)

    @pytest.mark.parametrize('query, error', (
        ('vals.#(b==~"invalid")', "Queries ==~ operator requires a boolean value, got <class 'str'> instead: invalid"),
    ))
    def test_get_raise(self, query, error):
        """It should raise a GJSONError error with the expected message."""
        with pytest.raises(gjson.GJSONError, match=re.escape(error)):
            self.object.get(query)


@pytest.mark.parametrize('modifier', ('@valid', '@this'))
def test_get_modifier_unmodified_ok(modifier):
    """It should return the same object."""
    obj = gjson.GJSON(INPUT_OBJECT)
    assert obj.get(modifier, quiet=True) == INPUT_OBJECT


def test_get_modifier_valid_raise():
    """It should return None if the object is invalid JSON and quiet is True."""
    obj = gjson.GJSON({'invalid': {1, 2}})
    assert obj.get('@valid', quiet=True) is None


@pytest.mark.parametrize('data, expected', (
    ('[3, 1, 5, 8, 2]', [1, 2, 3, 5, 8]),
    ('{"b": 2, "d": 4, "c": 3, "a": 1}', {"a": 1, "b": 2, "c": 3, "d": 4}),
    ('"a string"', None),
))
def test_get_modifier_sort(data, expected):
    """It should return the object sorted."""
    obj = gjson.GJSON(json.loads(data))
    compare_values(obj.get('@sort', quiet=True), expected)


def test_get_integer_index_on_mapping():
    """It should access the integer as string key correctly."""
    obj = gjson.GJSON(json.loads('{"1": 5, "11": 7}'))
    assert obj.get('1') == 5
    assert obj.get('11') == 7


def test_module_get():
    """It should return the queried object."""
    assert gjson.get({'key': 'value'}, 'key') == 'value'


def test_gjson_get_gjson():
    """It should return the queried object as a GJSON object."""
    ret = gjson.GJSON(INPUT_OBJECT).get_gjson('children')
    assert isinstance(ret, gjson.GJSON)
    assert str(ret) == '["Sara", "Alex", "Jack"]'


class TestJSONOutput:
    """Test class for all JSON output functionalities."""

    def setup_method(self):
        """Initialize the test instance."""
        self.obj = {'key': 'value'}
        self.query = 'key'
        self.value = '"value"'
        self.gjson = gjson.GJSON(self.obj)

    def test_module_get_as_str(self):
        """It should return the queried object as a JSON string."""
        assert gjson.get(self.obj, self.query, as_str=True) == self.value
        assert gjson.get(self.obj, '', as_str=True, quiet=True) == ''

    def test_gjson_getj(self):
        """It should return the queried object as a JSON string."""
        assert self.gjson.getj(self.query) == self.value
        assert self.gjson.getj('', quiet=True) == ''

    def test_module_get_as_str_raise(self):
        """It should raise a GJSONError with the proper message on failure."""
        with pytest.raises(gjson.GJSONError, match='Empty query.'):
            gjson.get(self.obj, '', as_str=True)

    def test_gjson_get_as_str_raise(self):
        """It should raise a GJSONError with the proper message on failure."""
        with pytest.raises(gjson.GJSONError, match='Empty query.'):
            self.gjson.getj('')

    @pytest.mark.parametrize('query, expected', (
        ('@pretty', '{\n  "key": "value"\n}'),
        ('@pretty:{"indent": 4}', '{\n    "key": "value"\n}'),
        ('@pretty:{"indent": "\t"}', '{\n\t"key": "value"\n}'),
    ))
    def test_modifier_pretty(self, query, expected):
        """It should prettyfy the JSON string based on the parameters."""
        assert self.gjson.getj(query) == expected

    def test_modifier_pretty_sort_keys_prefix(self):
        """It should prettyfy the JSON string and sort the keys."""
        output = gjson.GJSON({'key2': 'value2', 'key1': 'value1'}).getj('@pretty:{"sortKeys": true, "prefix": "## "}')
        assert output == '## {\n##   "key1": "value1",\n##   "key2": "value2"\n## }'

    def test_modifier_ugly(self):
        """It should uglyfy the JSON string."""
        assert gjson.get(self.obj, '@ugly', as_str=True) == '{"key":"value"}'


def custom_sum(options, obj, *, last):
    """Custom modifier function."""
    assert last is True
    assert options == {}
    if not isinstance(obj, list):
        raise RuntimeError('@sum can be used only on lists')

    return sum(obj)


class TestCustomModifiers:
    """Test class for custom modifiers."""

    def setup_method(self):
        """Initialize the test instance."""
        self.valid_obj = [1, 2, 3, 4, 5]
        self.invalid_obj = 'invalid'
        self.query = '@sum'

    def test_gjson_register_modifier_ok(self):
        """It should register a valid modifier."""
        obj = gjson.GJSON(self.valid_obj)
        obj.register_modifier('sum', custom_sum)
        assert obj.get(self.query) == 15

    def test_gjson_register_modifier_override_builtin(self):
        """It should raise a GJSONError if trying to register a modifier with the same name of a built-in one."""
        obj = gjson.GJSON(self.valid_obj)
        with pytest.raises(gjson.GJSONError,
                           match=r'Unable to register a modifier with the same name of the built-in modifier: @valid'):
            obj.register_modifier('valid', custom_sum)

    def test_gjson_register_modifier_not_callable(self):
        """It should raise a GJSONError if trying to register a modifier that is not callable."""
        obj = gjson.GJSON(self.valid_obj)
        with pytest.raises(gjson.GJSONError, match=r'The given func "not-callable" for the custom modifier @sum does'):
            obj.register_modifier('sum', 'not-callable')

    def test_gjsonobj_custom_modifiers_ok(self):
        """It should register a valid modifier."""
        obj = gjson.GJSONObj(self.valid_obj, self.query, custom_modifiers={'sum': custom_sum})
        assert obj.get() == 15

    def test_gjsonobj_custom_modifiers_raise(self):
        """It should encapsulate the modifier raised exception in a GJSONError."""
        with pytest.raises(gjson.GJSONError,
                           match=r'Modifier @sum raised an exception'):
            gjson.GJSONObj(self.invalid_obj, self.query, custom_modifiers={'sum': custom_sum}).get()

    def test_gjsonobj_custom_modifiers_override_builtin(self):
        """It should raise a GJSONError if passing custom modifiers that have the same name of a built-in one."""
        with pytest.raises(gjson.GJSONError,
                           match=r"Some provided custom_modifiers have the same name of built-in ones: {'valid'}"):
            gjson.GJSONObj(self.valid_obj, self.query, custom_modifiers={'valid': custom_sum})

    def test_gjsoniobj_custom_modifiers_not_callable(self):
        """It should raise a GJSONError if passing custom modifiers that are not callable."""
        with pytest.raises(gjson.GJSONError, match=r'The given func "not-callable" for the custom modifier @sum does'):
            gjson.GJSONObj(self.valid_obj, self.query, custom_modifiers={'sum': 'not-callable'})

    def test_gjsonobj_builtin_modifiers(self):
        """It should return a set with the names of the built-in modifiers."""
        expected = {'flatten', 'keys', 'pretty', 'reverse', 'sort', 'this', 'valid', 'values', 'ugly'}
        assert gjson.GJSONObj.builtin_modifiers() == expected


def test_cli_stdin(monkeypatch, capsys):
    """It should read the data from stdin and query it."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    ret = gjson.cli(['-', 'name.first'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Tom"\n'
    assert not captured.err


def test_cli_file(tmp_path, capsys):
    """It should read the data from the provided file and query it."""
    data_file = tmp_path / 'input.json'
    data_file.write_text(INPUT_JSON)
    ret = gjson.cli([str(data_file), 'name.first'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Tom"\n'
    assert not captured.err


def test_cli_nonexistent_file(tmp_path, capsys):
    """It should exit with a failure exit code and no output."""
    ret = gjson.cli([str(tmp_path / 'nonexistent.json'), 'name.first'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_cli_nonexistent_file_verbosity_1(tmp_path, capsys):
    """It should exit with a failure exit code and print the error message."""
    ret = gjson.cli(['-v', str(tmp_path / 'nonexistent.json'), 'name.first'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.startswith("ArgumentTypeError: can't open")
    assert 'nonexistent.json' in captured.err


def test_cli_nonexistent_file_verbosity_2(tmp_path):
    """It should raise the exception and print the full traceback."""
    with pytest.raises(
            argparse.ArgumentTypeError, match=r"can't open .*/nonexistent.json.* No such file or directory"):
        gjson.cli(['-vv', str(tmp_path / 'nonexistent.json'), 'name.first'])


def test_cli_stdin_query_verbosity_1(monkeypatch, capsys):
    """It should exit with a failure exit code and print the error message."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    ret = gjson.cli(['-v', '-', 'nonexistent'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == 'GJSONError: Mapping object does not have key nonexistent for query nonexistent\n'


def test_cli_stdin_query_verbosity_2(monkeypatch):
    """It should exit with a failure exit code and print the full traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    with pytest.raises(
            gjson.GJSONError, match=r'Mapping object does not have key nonexistent for query nonexistent'):
        gjson.cli(['-vv', '-', 'nonexistent'])


def test_cli_lines_ok(monkeypatch, capsys):
    """It should apply the same query to each line."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = gjson.cli(['--lines', '-', 'name'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Alexa"\n"May"\n"Deloise"\n'
    assert not captured.err


def test_cli_lines_failed_lines_verbosity_0(monkeypatch, capsys):
    """It should keep going with the other lines and just skip the failed line."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = gjson.cli(['--lines', '-', 'name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Deloise"\n'
    assert not captured.err


def test_cli_lines_failed_lines_verbosity_1(monkeypatch, capsys):
    """It should keep going with the other lines printing an error for the failed lines."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = gjson.cli(['-v', '--lines', '-', 'name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Deloise"\n'
    assert captured.err.count('JSONDecodeError') == 2


def test_cli_lines_failed_lines_verbosity_2(monkeypatch):
    """It should interrupt the processing and print the full traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    with pytest.raises(
            json.decoder.JSONDecodeError, match=r'Expecting property name enclosed in double quotes'):
        gjson.cli(['-vv', '--lines', '-', 'name'])


def test_cli_lines_double_dot_query(monkeypatch, capsys):
    """It should encapsulate each line in an array to allow queries."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = gjson.cli(['--lines', '..#(age>45).name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"May"\n'
    assert not captured.err


def test_cli_double_dot_query_ok(monkeypatch, capsys):
    """It should encapsulate the input in an array and apply the query to the array."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = gjson.cli(['-', '..#.name'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '["Gilbert", "Alexa", "May", "Deloise"]\n'
    assert not captured.err


def test_cli_double_dot_query_failed_lines_verbosity_0(monkeypatch, capsys):
    """It should encapsulate the input in an array skipping failing lines."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = gjson.cli(['-', '..#.name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_cli_double_dot_query_failed_lines_verbosity_1(monkeypatch, capsys):
    """It should encapsulate the input in an array skipping failing lines and printing an error for each failure."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = gjson.cli(['-v', '-', '..#.name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.startswith('JSONDecodeError: Expecting property name enclosed in double quotes')


def test_cli_double_dot_query_failed_lines_verbosity_2(monkeypatch):
    """It should interrupt the execution at the first invalid line and exit printing the traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    with pytest.raises(json.decoder.JSONDecodeError, match=r'Expecting property name enclosed in double quotes'):
        gjson.cli(['-vv', '-', '..#.name'])
