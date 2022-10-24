"""CLI test module."""
import argparse
import io
import json

import pytest

from gjson._cli import cli
from gjson.exceptions import GJSONParseError

from .test_init import INPUT_JSON, INPUT_LINES, INPUT_LINES_WITH_ERRORS


def test_cli_stdin(monkeypatch, capsys):
    """It should read the data from stdin and query it."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    ret = cli(['-', 'name.first'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Tom"\n'
    assert not captured.err


def test_cli_file(tmp_path, capsys):
    """It should read the data from the provided file and query it."""
    data_file = tmp_path / 'input.json'
    data_file.write_text(INPUT_JSON)
    ret = cli([str(data_file), 'name.first'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Tom"\n'
    assert not captured.err


def test_cli_nonexistent_file(tmp_path, capsys):
    """It should exit with a failure exit code and no output."""
    ret = cli([str(tmp_path / 'nonexistent.json'), 'name.first'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_cli_nonexistent_file_verbosity_1(tmp_path, capsys):
    """It should exit with a failure exit code and print the error message."""
    ret = cli(['-v', str(tmp_path / 'nonexistent.json'), 'name.first'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.startswith("ArgumentTypeError: can't open")
    assert 'nonexistent.json' in captured.err


def test_cli_nonexistent_file_verbosity_2(tmp_path):
    """It should raise the exception and print the full traceback."""
    with pytest.raises(
            argparse.ArgumentTypeError, match=r"can't open .*/nonexistent.json.* No such file or directory"):
        cli(['-vv', str(tmp_path / 'nonexistent.json'), 'name.first'])


def test_cli_stdin_query_verbosity_1(monkeypatch, capsys):
    """It should exit with a failure exit code and print the error message."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    ret = cli(['-v', '-', 'nonexistent'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == ('GJSONParseError: Mapping object does not have key `nonexistent`.\n'
                            'Query: nonexistent\n-------^\n')


def test_cli_stdin_query_verbosity_2(monkeypatch):
    """It should exit with a failure exit code and print the full traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_JSON))
    with pytest.raises(GJSONParseError, match=r'Mapping object does not have key `nonexistent`.'):
        cli(['-vv', '-', 'nonexistent'])


def test_cli_lines_ok(monkeypatch, capsys):
    """It should apply the same query to each line."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = cli(['--lines', '-', 'name'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Alexa"\n"May"\n"Deloise"\n'
    assert not captured.err


def test_cli_lines_failed_lines_verbosity_0(monkeypatch, capsys):
    """It should keep going with the other lines and just skip the failed line."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = cli(['--lines', '-', 'name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Deloise"\n'
    assert not captured.err


def test_cli_lines_failed_lines_verbosity_1(monkeypatch, capsys):
    """It should keep going with the other lines printing an error for the failed lines."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = cli(['-v', '--lines', '-', 'name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"Deloise"\n'
    assert captured.err.count('JSONDecodeError') == 2


def test_cli_lines_failed_lines_verbosity_2(monkeypatch):
    """It should interrupt the processing and print the full traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    with pytest.raises(
            json.decoder.JSONDecodeError, match=r'Expecting property name enclosed in double quotes'):
        cli(['-vv', '--lines', '-', 'name'])


def test_cli_lines_double_dot_query(monkeypatch, capsys):
    """It should encapsulate each line in an array to allow queries."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = cli(['--lines', '..#(age>45).name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == '"Gilbert"\n"May"\n'
    assert not captured.err


def test_cli_double_dot_query_ok(monkeypatch, capsys):
    """It should encapsulate the input in an array and apply the query to the array."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES))
    ret = cli(['-', '..#.name'])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == '["Gilbert", "Alexa", "May", "Deloise"]\n'
    assert not captured.err


def test_cli_double_dot_query_failed_lines_verbosity_0(monkeypatch, capsys):
    """It should encapsulate the input in an array skipping failing lines."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = cli(['-', '..#.name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_cli_double_dot_query_failed_lines_verbosity_1(monkeypatch, capsys):
    """It should encapsulate the input in an array skipping failing lines and printing an error for each failure."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    ret = cli(['-v', '-', '..#.name'])
    assert ret == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.startswith('JSONDecodeError: Expecting property name enclosed in double quotes')


def test_cli_double_dot_query_failed_lines_verbosity_2(monkeypatch):
    """It should interrupt the execution at the first invalid line and exit printing the traceback."""
    monkeypatch.setattr('sys.stdin', io.StringIO(INPUT_LINES_WITH_ERRORS))
    with pytest.raises(json.decoder.JSONDecodeError, match=r'Expecting property name enclosed in double quotes'):
        cli(['-vv', '-', '..#.name'])
