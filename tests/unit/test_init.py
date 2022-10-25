"""GJSON test module."""
# pylint: disable=attribute-defined-outside-init
import json
import re

from collections.abc import Mapping

import pytest

import gjson
from gjson._gjson import MODIFIER_NAME_RESERVED_CHARS


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
        "keyk*":{"key?":"val7"},
        "1key":"val8"
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
INPUT_SUM_N = json.loads("""
[
    {"key": "a", "value": 1, "other": "value"},
    {"key": "b", "value": 2},
    {"key": "c", "value": 3, "other": "value"},
    {"key": "a", "value": 7},
    {"key": "b", "value": 1.5},
    {"key": "d", "value": 4},
    {"key": "c", "value": 9}
]
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
        ('friends.#(last=="Murphy").first', 'Dale'),
        ('friends.#(last=="Murphy")#.first', ['Dale', 'Jane']),
        ('friends.#(=="Murphy")#', []),
        ('friends.#(=="Mu)(phy")#', []),
        ('friends.#(age\\===44)#', []),
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
        ('@pretty:{"indent": 4}', INPUT_OBJECT),
        (r'fav\.movie.@pretty:{"indent": 4}', 'Deer Hunter'),
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
        ('age.0', "Integer query part on unsupported object type <class 'int'>"),
        ('friends.99', 'Index `99` out of range for sequence object with 3 items in query.'),
        ('name.nonexistent', 'Mapping object does not have key `nonexistent`.'),
        ('name.1', 'Mapping object does not have key `1`.'),
        ('children.invalid', 'Invalid or unsupported query part `invalid`.'),
        ('children.', 'Delimiter at the end of the query.'),
        ('children\\', 'Escape character at the end of the query.'),
        # Wildcards
        ('x*', 'No key matching pattern with wildcard `x*`'),
        ('??????????', 'No key matching pattern with wildcard `??????????`'),
        ('children.x*', "Wildcard matching key `x*` requires a mapping object, got <class 'list'> instead."),
        ('(-?', 'No key matching pattern with wildcard `(-?`'),
        # Queries
        ('#', "Expected a sequence like object for query part # at the end of the query, got <class 'dict'>."),
        ('#.invalid', 'Invalid or unsupported query part `invalid`.'),
        ('friends.#(=="Murphy")', 'Query on mapping like objects require a key before the operator.'),
        ('friends.#(last=={1: 2})', 'Invalid value `{1: 2}` for the query key `last`'),
        ('friends.#(invalid', "Unbalanced parentheses, opened ['('] vs closed []"),
        ('#(first)', 'Queries are supported only for sequence like objects'),
        ('friends.#(last=="invalid")', 'Query for first element does not match anything.'),
        ('friends.#(first%"D?")', 'Query for first element does not match anything.'),
        ('friends.#(last=="Murphy")invalid', 'Expected delimiter or end of query after closing parenthesis.'),
        ('children.#()', 'Empty or invalid query.'),
        ('children.#()#', 'Empty or invalid query.'),
        ('friends.#.invalid.#()', 'Empty or invalid query.'),
        ('friends.#.invalid.#()#', 'Empty or invalid query.'),
        # Dot vs Pipe
        ('friends.#(last="Murphy")#|first', 'Invalid or unsupported query'),
        # Modifiers
        ('@', 'Got empty modifier name.'),
        ('friends.@', 'Got empty modifier name.'),
        ('friends.@pretty:', 'Modifier with options separator `:` without any option.'),
        ('friends.@pretty:{invalid', 'Unable to load modifier options.'),
        ('friends.@pretty:["invalid"]', "Expected JSON object `{...}` as modifier options."),
        ('friends.@invalid', 'Unknown modifier @invalid.'),
        ('friends.@in"valid', 'Invalid modifier name @in"valid, the following characters are not allowed'),
        # JSON Lines
        ('..name', 'Invalid query with two consecutive path delimiters.'),
    ))
    def test_get_parser_raise(self, query, error):
        """It should raise a GJSONParseError error with the expected message."""
        with pytest.raises(gjson.GJSONParseError, match=re.escape(error)):
            self.object.get(query)

    @pytest.mark.parametrize('query, error', (
        # Basic
        ('', 'Empty query.'),
        # Modifiers
        ('children.@keys', 'The current object does not have a keys() method.'),
        ('children.@values', 'The current object does not have a values() method.'),
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
        ('test.1key', 'val8'),
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
        ('#|first', 'Invalid or unsupported query part `first`.'),
        ('#|0', 'Integer query part after a pipe delimiter on an sequence like object.'),
        ('#|#', 'The pipe delimiter cannot immediately follow the # element.'),
    ))
    def test_get_raise(self, query, error):
        """It should raise a GJSONError error with the expected message."""
        with pytest.raises(gjson.GJSONParseError, match=re.escape(error)):
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
        ('vals.#(b==~"invalid")',
         "Queries ==~ operator requires a boolean value, got <class 'str'> instead: `invalid`"),
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


@pytest.mark.parametrize('data, num, expected', (
    # Valid data
    ('[1, 2, 3, 4, 5]', None, {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}),
    ('[1, 2, 3, 4, 5]', 0, {}),
    ('[1, 2, 3, 4, 5]', 2, {1: 1, 2: 1}),
    ('[1, 1, 1, 1, 1]', None, {1: 5}),
    ('[1, 1, 1, 1, 1]', 1, {1: 5}),
    ('[1, 1, 1, 2, 2, 3]', None, {1: 3, 2: 2, 3: 1}),
    ('[1, 1, 1, 2, 2, 3, 3, 3, 3]', None, {3: 4, 1: 3, 2: 2}),
    ('[1, 1, 1, 2, 2, 3, 3, 3, 3]', 2, {3: 4, 1: 3}),
    # Invalid data
    ('{"key": "value"}', None, None),
    ('1', None, None),
    ('"value"', None, None),
))
def test_get_modifier_top_n(data, num, expected):
    """It should return the top N common items."""
    obj = gjson.GJSON(json.loads(data))
    if num is not None:
        compare_values(obj.get(f'@top_n:{{"n": {num}}}', quiet=True), expected)
    else:
        compare_values(obj.get('@top_n', quiet=True), expected)


@pytest.mark.parametrize('num, expected', (
    (0, {}),
    (1, {"c": 12}),
    (2, {"c": 12, "a": 8}),
    (3, {"c": 12, "a": 8, "d": 4}),
    (4, {"c": 12, "a": 8, "d": 4, "b": 3.5}),
    (None, {"c": 12, "a": 8, "d": 4, "b": 3.5}),
))
def test_get_modifier_sum_n_valid(num, expected):
    """It should group and sum and return the top N items."""
    obj = gjson.GJSON(INPUT_SUM_N)
    if num is not None:
        compare_values(obj.get(f'@sum_n:{{"group": "key", "sum": "value", "n": {num}}}', quiet=True), expected)
    else:
        compare_values(obj.get('@sum_n:{"group": "key", "sum": "value"}', quiet=True), expected)


@pytest.mark.parametrize('data', (
    '{"an": "object"}',
    '"a string"',
    '1',
))
def test_get_modifier_sum_n_invalid_data(data):
    """It should raise a GJSONError if the input is invalid."""
    obj = gjson.GJSON(json.loads(data))
    with pytest.raises(gjson.GJSONError, match="@sum_n modifier not supported for object of type"):
        obj.get('@sum_n:{"group": "key", "sum": "value"}')


@pytest.mark.parametrize('options', (
    '',
    ':{}',
    ':{"group": "invalid", "sum": "value"}',
    ':{"group": "key", "sum": "invalid"}',
    ':{"group": "key", "sum": "other"}',
    ':{"group": "other", "sum": "value"}',
))
def test_get_modifier_sum_n_invalid_options(options):
    """It should raise a GJSONError if the options are invalid."""
    obj = gjson.GJSON(INPUT_SUM_N)
    with pytest.raises(gjson.GJSONError, match="Modifier @sum_n raised an exception"):
        obj.get(f'@sum_n{options}')


class TestJSONOutput:
    """Test class for all JSON output functionalities."""

    def setup_method(self):
        """Initialize the test instance."""
        self.obj = {'key': 'value', 'hello world': '\u3053\u3093\u306b\u3061\u306f\u4e16\u754c'}
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
        ('@pretty', '{\n  "key": "value",\n  "hello world": "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"\n}'),
        ('@pretty:{"indent": 4}',
         '{\n    "key": "value",\n    "hello world": "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"\n}'),
        ('@pretty:{"indent": "\t"}',
         '{\n\t"key": "value",\n\t"hello world": "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"\n}'),
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
        assert gjson.get(self.obj, '@ugly', as_str=True) == (
            '{"key":"value","hello world":"\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"}')

    def test_output_unicode(self):
        """It should return unicode characters as-is."""
        assert gjson.get(self.obj, 'hello world', as_str=True) == '"\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"'

    def test_modifier_ascii(self):
        """It should escape all non-ASCII characters."""
        assert gjson.get(self.obj, 'hello world.@ascii', as_str=True) == (
            '"\\u3053\\u3093\\u306b\\u3061\\u306f\\u4e16\\u754c"')


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

    def test_gjson_register_modifier_with_escape_ok(self):
        """It should register a valid modifier with escaped characters in the name."""
        obj = gjson.GJSON(self.valid_obj)
        obj.register_modifier('sum\\=', custom_sum)
        assert obj.get('@sum\\=') == 15

    @pytest.mark.parametrize('char', MODIFIER_NAME_RESERVED_CHARS)
    def test_gjson_register_modifier_invalid_name(self, char):
        """It should raise a GJSONError if trying to register a modifier with a name with not allowed characters."""
        obj = gjson.GJSON(self.valid_obj)
        name = fr'a{char}b'
        with pytest.raises(
                gjson.GJSONError,
                match=fr'Unable to register modifier `{re.escape(name)}`, contains at least one not allowed'):
            obj.register_modifier(name, custom_sum)

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
        expected = {'ascii', 'flatten', 'keys', 'pretty', 'reverse', 'sort', 'sum_n', 'this', 'top_n', 'valid',
                    'values', 'ugly'}
        assert gjson.GJSONObj.builtin_modifiers() == expected
