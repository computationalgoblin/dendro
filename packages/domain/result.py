"""
Result type for narrative-architect.

Generic Result type that represents either a success (Ok) or failure (Error).
Inspired by Rust's Result<T, E> pattern. Avoids using exceptions for control flow.

Usage:
    result = divide(10, 2)
    if result.is_ok():
        print(result.unwrap())
    elif result.is_error():
        print(result.unwrap_error())
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


class _ResultType(Generic[T, E]):
    """Base class for Result variants. Not intended for direct instantiation."""

    __slots__ = ()


@dataclasses.dataclass(frozen=True)
class Ok(_ResultType[T, E]):
    """Represents a successful result containing a value of type T."""

    value: T

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


@dataclasses.dataclass(frozen=True)
class Error(_ResultType[T, E]):
    """Represents a failed result containing an error of type E."""

    error: E

    def __repr__(self) -> str:
        return f"Error({self.error!r})"


Result = Union[Ok[T, E], Error[T, E]]
"""Type alias for the Result monad: either Ok[T, E] or Error[T, E]."""


def ok_result(value: T) -> Ok[T, E]:
    """Create an Ok result. Convenience factory."""
    return Ok(value)


def error_result(error: E) -> Error[T, E]:
    """Create an Error result. Convenience factory."""
    return Error(error)


# --- Utility functions ---


def is_ok(result: Result[T, E]) -> bool:
    """Check if a Result is an Ok variant."""
    return isinstance(result, Ok)


def is_error(result: Result[T, E]) -> bool:
    """Check if a Result is an Error variant."""
    return isinstance(result, Error)


def unwrap(result: Result[T, E]) -> T:
    """Unwrap an Ok value, raising TypeError if it's an Error."""
    if isinstance(result, Ok):
        return result.value
    raise TypeError(f"Called unwrap on Error: {result.error}")


def unwrap_error(result: Result[T, E]) -> E:
    """Unwrap an Error value, raising TypeError if it's an Ok."""
    if isinstance(result, Error):
        return result.error
    raise TypeError(f"Called unwrap_error on Ok: {result}")


def map_result(result: Result[T, E], fn: Callable[[T], U]) -> Result[U, E]:
    """Apply a function to the Ok value, preserving Error."""
    if isinstance(result, Ok):
        return Ok(fn(result.value))
    return result  # type: ignore


def map_error_result(result: Result[T, E], fn: Callable[[E], U]) -> Result[T, U]:
    """Apply a function to the Error value, preserving Ok."""
    if isinstance(result, Error):
        return Error(fn(result.error))
    return result  # type: ignore


def chain_result(result: Result[T, E], fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
    """Chain a Result-returning function, propagating errors."""
    if isinstance(result, Ok):
        return fn(result.value)
    return result  # type: ignore


__all__ = [
    "Ok",
    "Error",
    "Result",
    "ok_result",
    "error_result",
    "is_ok",
    "is_error",
    "unwrap",
    "unwrap_error",
    "map_result",
    "map_error_result",
    "chain_result",
]
