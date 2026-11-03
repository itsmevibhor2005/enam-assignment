"""Model output is untrusted input."""
from app.llm.client import parse_json_loose


def test_plain_json():
    assert parse_json_loose('{"a": 1}') == {"a": 1}


def test_markdown_fenced():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}


def test_leading_prose():
    assert parse_json_loose('Here is the result:\n{"a": 1}') == {"a": 1}


def test_trailing_commentary():
    assert parse_json_loose('{"a": 1}\n\nLet me know if you need more.') == {"a": 1}


def test_trailing_comma_is_repaired():
    assert parse_json_loose('{"a": 1,}') == {"a": 1}


def test_array_root():
    assert parse_json_loose('[{"a": 1}]') == [{"a": 1}]


def test_unrecoverable_returns_none():
    assert parse_json_loose("I could not complete that request.") is None
    assert parse_json_loose("") is None
