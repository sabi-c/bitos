"""Tiny requests-compat shim for test/runtime environments without requests package."""

from __future__ import annotations

import httpx


class Response:
    def __init__(self, response: httpx.Response):
        self._response = response
        self.status_code = response.status_code

    def json(self):
        return self._response.json()

    def raise_for_status(self):
        self._response.raise_for_status()


def get(url: str, params=None, timeout: float = 10):
    return Response(httpx.get(url, params=params, timeout=timeout))


def post(url: str, params=None, json=None, timeout: float = 10):
    return Response(httpx.post(url, params=params, json=json, timeout=timeout))
