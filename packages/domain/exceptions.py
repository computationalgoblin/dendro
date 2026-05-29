"""
Base exception hierarchy for narrative-architect.

Provides DomainError (for domain-level rule violations) and ApplicationError
(for application service violations), plus a generic NarrativeArchitectError
base class that all project exceptions extend.

All custom exceptions should inherit from these base classes so that
exception handling can be done at the appropriate level of abstraction
without leaking implementation details.
"""

from __future__ import annotations


class NarrativeArchitectError(Exception):
    """Base exception for all narrative-architect errors.

    All custom exceptions in the project should inherit from this class
    (directly or through DomainError/ApplicationError) to ensure consistent
    error handling and traceability.
    """

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return f"[{self.code}] {self.message}"

    @property
    def error_code(self) -> str:
        return self.code


class DomainError(NarrativeArchitectError):
    """Exception for domain rule violations.

    Raised when a domain invariant is violated (e.g., invalid entity name,
    invalid relation type, canon state transition not allowed).
    These represent bugs in the domain logic or invalid input data.

    Code prefix: DOMAIN_
    """


class ApplicationError(NarrativeArchitectError):
    """Exception for application service violations.

    Raised when an application-level rule is violated (e.g., unauthorized
    access, invalid command, concurrent modification).
    These represent usage errors or authorization failures.

    Code prefix: APP_
    """


class ConfigurationError(NarrativeArchitectError):
    """Exception for configuration errors.

    Raised when the application configuration is invalid, missing, or
    inconsistent. Typically caught at startup or when loading settings.

    Code prefix: CONFIG_
    """


class PersistenceError(NarrativeArchitectError):
    """Exception for persistence layer errors.

    Raised when data storage or retrieval fails (e.g., file not found,
    corrupt data, schema version mismatch).
    Not part of the domain layer -- defined here for import convenience.

    Code prefix: PERSIST_
    """


__all__ = [
    "NarrativeArchitectError",
    "DomainError",
    "ApplicationError",
    "ConfigurationError",
    "PersistenceError",
]
