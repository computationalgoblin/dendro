"""Tests for the Result type."""

import dataclasses

from packages.domain.result import (
    Error,
    Ok,
    chain_result,
    is_error,
    is_ok,
    map_error_result,
    map_result,
    unwrap,
    unwrap_error,
)


class TestResultCreation:
    """Test basic Result creation and type checking."""

    def test_ok_creation(self):
        result: Ok[int, str] = Ok(42)
        assert is_ok(result)
        assert not is_error(result)
        assert result.value == 42

    def test_error_creation(self):
        result: Error[int, str] = Error("something went wrong")
        assert is_error(result)
        assert not is_ok(result)
        assert result.error == "something went wrong"

    def test_ok_with_string(self):
        result = Ok("hello")
        assert is_ok(result)
        assert result.value == "hello"

    def test_error_with_int_code(self):
        result = Error(404)
        assert is_error(result)
        assert result.error == 404

    def test_ok_with_none(self):
        result = Ok(None)
        assert is_ok(result)
        assert result.value is None

    def test_ok_with_complex_type(self):
        result = Ok({"key": "value", "count": 3})
        assert is_ok(result)
        assert result.value["key"] == "value"
        assert result.value["count"] == 3


class TestResultUnwrap:
    """Test unwrap operations."""

    def test_unwrap_ok(self):
        result = Ok(42)
        assert unwrap(result) == 42

    def test_unwrap_error_raises(self):
        result = Error("fail")
        try:
            unwrap(result)
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "Error" in str(e)

    def test_unwrap_error_value(self):
        result = Error("fail")
        assert unwrap_error(result) == "fail"

    def test_unwrap_error_on_ok_raises(self):
        result = Ok(42)
        try:
            unwrap_error(result)
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "Ok" in str(e)


class TestResultMap:
    """Test mapping operations on Results."""

    def test_map_ok(self):
        result = Ok(21)
        doubled = map_result(result, lambda x: x * 2)
        assert is_ok(doubled)
        assert unwrap(doubled) == 42

    def test_map_error_preserved(self):
        result = Error("fail")
        doubled = map_result(result, lambda x: x * 2)
        assert is_error(doubled)
        assert unwrap_error(doubled) == "fail"

    def test_map_error_ok_preserved(self):
        result = Ok(42)
        mapped = map_error_result(result, lambda e: f"mapped: {e}")
        assert is_ok(mapped)
        assert unwrap(mapped) == 42

    def test_map_error_on_error(self):
        result = Error("original error")
        mapped = map_error_result(result, lambda e: f"mapped: {e}")
        assert is_error(mapped)
        assert unwrap_error(mapped) == "mapped: original error"


class TestResultChain:
    """Test chaining operations on Results."""

    def test_chain_ok_to_ok(self):
        result = Ok(5)

        def divide_by_two(x: int) -> Ok[int, str]:
            return Ok(x // 2)

        chained = chain_result(result, divide_by_two)
        assert is_ok(chained)
        assert unwrap(chained) == 2

    def test_chain_ok_to_error(self):
        result = Ok(5)

        def fail_if_odd(x: int) -> Error[int, str]:
            return Error(f"{x} is odd")

        chained = chain_result(result, fail_if_odd)
        assert is_error(chained)
        assert unwrap_error(chained) == "5 is odd"

    def test_chain_error_short_circuits(self):
        result = Error("original error")

        def should_not_be_called(x: int) -> Ok[int, str]:
            raise AssertionError("This should not be called")

        chained = chain_result(result, should_not_be_called)
        assert is_error(chained)
        assert unwrap_error(chained) == "original error"


class TestResultImmutability:
    """Test Result immutability (frozen dataclass)."""

    def test_ok_is_frozen(self):
        result = Ok(42)
        try:
            result.value = 43
            assert False, "Should have raised FrozenInstanceError"
        except (dataclasses.FrozenInstanceError, AttributeError):
            pass

    def test_error_is_frozen(self):
        result = Error("msg")
        try:
            result.error = "new msg"
            assert False, "Should have raised FrozenInstanceError"
        except (dataclasses.FrozenInstanceError, AttributeError):
            pass


class TestResultEdgeCases:
    """Test edge cases for Result type."""

    def test_ok_with_empty_string(self):
        result = Ok("")
        assert is_ok(result)
        assert result.value == ""

    def test_error_with_empty_string(self):
        result = Error("")
        assert is_error(result)
        assert result.error == ""

    def test_ok_repr(self):
        result = Ok(42)
        assert repr(result) == "Ok(42)"

    def test_error_repr(self):
        result = Error("fail")
        assert repr(result) == "Error('fail')"
