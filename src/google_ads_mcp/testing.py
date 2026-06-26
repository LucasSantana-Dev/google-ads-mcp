"""Test doubles. ``FakeGoogleAdsClient`` mimics the subset of GoogleAdsClient our tools use,
so tools can be unit-tested without network or credentials.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _Batch:
    def __init__(self, rows: list) -> None:
        self.results = list(rows)


class _GoogleAdsService:
    def __init__(self, rows: list, batch_size: int | None = None) -> None:
        self._rows = rows
        self._batch_size = batch_size

    def search_stream(self, customer_id: str | None = None, query: str | None = None):
        if self._batch_size:
            for i in range(0, len(self._rows), self._batch_size):
                yield _Batch(self._rows[i : i + self._batch_size])
        else:
            yield _Batch(self._rows)


class _CustomerService:
    def __init__(self, resource_names: list) -> None:
        self._resource_names = list(resource_names)

    def list_accessible_customers(self):
        return SimpleNamespace(resource_names=self._resource_names)


class _FieldService:
    def __init__(self, fields: list) -> None:
        self._fields = list(fields)

    def search_google_ads_fields(self, query: str | None = None, request: Any = None):
        return list(self._fields)


class FakeGoogleAdsClient:
    """Configurable stand-in for ``google.ads.googleads.client.GoogleAdsClient``.

    Args:
        rows: dicts returned by ``GoogleAdsService.search_stream`` (passed through by row_to_dict).
        customers: resource-name strings for ``CustomerService.list_accessible_customers``.
        fields: objects (e.g. ``SimpleNamespace(name=..., category=...)``) for
            ``GoogleAdsFieldService.search_google_ads_fields``.
        batch_size: if set, split rows into multiple stream batches (exercises pagination).
    """

    def __init__(
        self,
        *,
        rows: list | None = None,
        customers: list | None = None,
        fields: list | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._rows = rows or []
        self._customers = customers or []
        self._fields = fields or []
        self._batch_size = batch_size

    def get_service(self, name: str):
        if name == "GoogleAdsService":
            return _GoogleAdsService(self._rows, self._batch_size)
        if name == "CustomerService":
            return _CustomerService(self._customers)
        if name == "GoogleAdsFieldService":
            return _FieldService(self._fields)
        raise ValueError(f"FakeGoogleAdsClient has no service {name!r}")
