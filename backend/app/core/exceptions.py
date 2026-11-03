"""Domain exceptions, mapped to HTTP responses in app.main."""
from __future__ import annotations


class FinnError(Exception):
    """Base for everything this application raises deliberately."""

    status_code = 500
    message = "Something went wrong."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class UpstreamUnavailable(FinnError):
    status_code = 503
    message = "An upstream data source could not be reached."


class TickerNotFound(FinnError):
    status_code = 404
    message = "No data available for that ticker."


class InsufficientData(FinnError):
    status_code = 422
    message = "Not enough primary-source data to produce this analysis."


class LLMUnavailable(FinnError):
    status_code = 503
    message = "No language-model provider is configured."
