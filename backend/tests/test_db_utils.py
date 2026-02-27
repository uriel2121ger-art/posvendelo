"""Unit tests for db/connection.py utility functions (no DB needed)."""

import pytest
from db.connection import _named_to_positional, escape_like


class TestNamedToPositional:
    def test_basic(self):
        sql, args = _named_to_positional(
            "SELECT * FROM t WHERE a = :a AND b = :b", {"a": 1, "b": "x"}
        )
        assert sql == "SELECT * FROM t WHERE a = $1 AND b = $2"
        assert args == [1, "x"]

    def test_repeated_param(self):
        sql, args = _named_to_positional(
            "SELECT * FROM t WHERE a = :a OR b = :a", {"a": 42}
        )
        assert sql == "SELECT * FROM t WHERE a = $1 OR b = $1"
        assert args == [42]

    def test_cast_not_confused(self):
        sql, args = _named_to_positional(
            "INSERT INTO t (data) VALUES (:data::jsonb)", {"data": "{}"}
        )
        assert "::jsonb" in sql
        assert "$1" in sql
        assert args == ["{}"]

    def test_string_literal_not_replaced(self):
        sql, args = _named_to_positional(
            "SELECT ':name' AS label, :val AS v", {"val": 1}
        )
        assert "':name'" in sql
        assert args == [1]

    def test_missing_key_raises(self):
        with pytest.raises(KeyError, match="a"):
            _named_to_positional("SELECT :a", {"b": 1})

    def test_multiple_casts(self):
        sql, args = _named_to_positional(
            "SELECT :x::int + :y::numeric", {"x": 1, "y": 2}
        )
        assert "::int" in sql
        assert "::numeric" in sql
        assert args == [1, 2]

    def test_empty_params(self):
        sql, args = _named_to_positional("SELECT 1", {})
        assert sql == "SELECT 1"
        assert args == []

    def test_order_preserved(self):
        sql, args = _named_to_positional(
            "INSERT INTO t (a, b, c) VALUES (:c, :a, :b)",
            {"a": 1, "b": 2, "c": 3},
        )
        # c appears first → $1, a → $2, b → $3
        assert args == [3, 1, 2]


class TestEscapeLike:
    def test_percent(self):
        assert escape_like("50%") == "50\\%"

    def test_underscore(self):
        assert escape_like("a_b") == "a\\_b"

    def test_backslash(self):
        assert escape_like("a\\b") == "a\\\\b"

    def test_combined(self):
        assert escape_like("50%_\\x") == "50\\%\\_\\\\x"

    def test_clean_string(self):
        assert escape_like("hello") == "hello"
