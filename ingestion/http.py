"""Small HTTP helper for polite, repeatable open-data ingestion."""

from __future__ import annotations

import json
import io
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, TextIO


DEFAULT_USER_AGENT = "ArtMarketIntelligence/0.1 (+https://github.com/lmc85/art-market-intelligence)"


class HttpError(RuntimeError):
    """Raised when an HTTP request fails after retries."""


@dataclass
class HttpClient:
    """Tiny JSON client with source-friendly defaults and retry behavior."""

    timeout_seconds: int = 20
    retries: int = 2
    backoff_seconds: float = 0.75
    user_agent: str = DEFAULT_USER_AGENT
    headers: Dict[str, str] = field(default_factory=dict)

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self.get_text(url, params=params)
        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise HttpError(f"Response from {url} was not valid JSON") from exc

    def get_text(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        request_url = self._with_params(url, params)
        request = urllib.request.Request(request_url, headers=self._headers())
        last_error: Optional[BaseException] = None

        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return response.read().decode("utf-8")
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(self.backoff_seconds * (attempt + 1))

        raise HttpError(f"GET failed for {request_url}: {last_error}")

    @contextmanager
    def open_text_stream(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[TextIO]:
        """Open a text response without reading it fully into memory."""

        request_url = self._with_params(url, params)
        request = urllib.request.Request(request_url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            yield io.TextIOWrapper(response, encoding=encoding, newline="")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json,text/csv,text/plain;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }
        headers.update(self.headers)
        return headers

    @staticmethod
    def _with_params(url: str, params: Optional[Dict[str, Any]]) -> str:
        if not params:
            return url

        clean_params = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        if not clean_params:
            return url

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{urllib.parse.urlencode(clean_params)}"
