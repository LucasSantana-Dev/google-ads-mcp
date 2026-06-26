"""Test doubles. ``FakeGoogleAdsClient`` mimics the subset of GoogleAdsClient our tools use
(reads and status mutations), so tools can be unit-tested without network or credentials.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _NestedNamespace:
    """Recursive auto-creating namespace for proto-plus-like types in tests."""

    def __getattr__(self, name: str):
        child = _NestedNamespace()
        object.__setattr__(self, name, child)
        return child

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)

    def __int__(self) -> int:
        return 0

    def __str__(self) -> str:
        return ""

    def __bool__(self) -> bool:
        return True

    def append(self, item: Any) -> None:
        lst = object.__getattribute__(self, "_list") if "_list" in self.__dict__ else []
        lst.append(item)
        object.__setattr__(self, "_list", lst)

    def __iter__(self):
        return iter(self.__dict__.get("_list", []))


# --- read side ------------------------------------------------------------

class _Batch:
    def __init__(self, rows: list) -> None:
        self.results = list(rows)


class _GoogleAdsService:
    def __init__(self, rows: list, batch_size: int | None = None, recorder: list | None = None) -> None:
        self._rows = rows
        self._batch_size = batch_size
        self._recorder = recorder if recorder is not None else []

    def search_stream(self, customer_id: str | None = None, query: str | None = None):
        if self._batch_size:
            for i in range(0, len(self._rows), self._batch_size):
                yield _Batch(self._rows[i : i + self._batch_size])
        else:
            yield _Batch(self._rows)

    def mutate(self, customer_id: str | None = None, mutate_operations: list | None = None,
               validate_only: bool = False, partial_failure: bool = False):
        ops = list(mutate_operations or [])
        self._recorder.append({
            "method": "mutate",
            "customer_id": customer_id,
            "validate_only": validate_only,
            "op_count": len(ops),
        })
        responses = []
        for i, op in enumerate(ops):
            resp = _NestedNamespace()
            resp.campaign_budget_result = _NestedNamespace()
            resp.campaign_budget_result.resource_name = f"customers/{customer_id}/campaignBudgets/{i}"
            resp.campaign_result = _NestedNamespace()
            resp.campaign_result.resource_name = f"customers/{customer_id}/campaigns/{i}"
            resp.ad_group_result = _NestedNamespace()
            resp.ad_group_result.resource_name = f"customers/{customer_id}/adGroups/{i}"
            resp.ad_group_criterion_result = _NestedNamespace()
            resp.ad_group_criterion_result.resource_name = f"customers/{customer_id}/adGroupCriteria/{i}"
            resp.ad_group_ad_result = _NestedNamespace()
            resp.ad_group_ad_result.resource_name = f"customers/{customer_id}/adGroupAds/{i}"
            responses.append(resp)
        return SimpleNamespace(mutate_operation_responses=responses)


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


# --- write side -----------------------------------------------------------

class _Operation:
    """Stand-in for a *Operation proto-plus message used by status mutations."""

    def __init__(self) -> None:
        self.update = SimpleNamespace(resource_name=None, status=None)
        self.update_mask = SimpleNamespace(paths=[])
        self.create = _NestedNamespace()
        self.campaign_budget_operation = SimpleNamespace(create=_NestedNamespace())
        self.campaign_operation = SimpleNamespace(create=_NestedNamespace())
        self.ad_group_operation = SimpleNamespace(create=_NestedNamespace())
        self.ad_group_criterion_operation = SimpleNamespace(create=_NestedNamespace())
        self.ad_group_ad_operation = SimpleNamespace(create=_NestedNamespace())


class _Enums:
    """client.enums.<SomeStatusEnum>.PAUSED -> "PAUSED" (value identity is enough for tests)."""

    def __getattr__(self, enum_name: str):
        if enum_name == "BudgetDeliveryMethodEnum":
            return SimpleNamespace(STANDARD="STANDARD")
        if enum_name == "CampaignStatusEnum":
            return SimpleNamespace(ENABLED="ENABLED", PAUSED="PAUSED", REMOVED="REMOVED")
        if enum_name == "AdvertisingChannelTypeEnum":
            return SimpleNamespace(SEARCH="SEARCH", DISPLAY="DISPLAY", SHOPPING="SHOPPING", VIDEO="VIDEO", PERFORMANCE_MAX="PERFORMANCE_MAX")
        if enum_name == "AdGroupStatusEnum":
            return SimpleNamespace(ENABLED="ENABLED", PAUSED="PAUSED", REMOVED="REMOVED")
        if enum_name == "AdGroupCriterionStatusEnum":
            return SimpleNamespace(ENABLED="ENABLED", PAUSED="PAUSED", REMOVED="REMOVED")
        if enum_name == "KeywordMatchTypeEnum":
            return SimpleNamespace(BROAD="BROAD", PHRASE="PHRASE", EXACT="EXACT")
        if enum_name == "AdGroupAdStatusEnum":
            return SimpleNamespace(ENABLED="ENABLED", PAUSED="PAUSED", REMOVED="REMOVED")
        return SimpleNamespace(ENABLED="ENABLED", PAUSED="PAUSED", REMOVED="REMOVED")


class _MutateService:
    """Generic stand-in for entity services: provides *_path builders and mutate_* methods."""

    def __init__(self, recorder: list) -> None:
        self._recorder = recorder

    def __getattr__(self, name: str):
        if name.endswith("_path"):
            return lambda customer_id, *ids: (
                f"customers/{customer_id}/" + "/".join(str(i) for i in ids)
            )
        if name.startswith("mutate_"):
            def _mutate(customer_id=None, operations=None, validate_only=False):
                ops = list(operations or [])
                self._recorder.append(
                    {
                        "method": name,
                        "customer_id": customer_id,
                        "validate_only": validate_only,
                        "op_count": len(ops),
                    }
                )
                results = [
                    SimpleNamespace(resource_name=getattr(op.update, "resource_name", None))
                    for op in ops
                ]
                return SimpleNamespace(results=results)

            return _mutate
        raise AttributeError(name)


class FakeGoogleAdsClient:
    """Configurable stand-in for ``google.ads.googleads.client.GoogleAdsClient``.

    Args:
        rows: dicts returned by ``GoogleAdsService.search_stream`` (passed through by row_to_dict).
        customers: resource-name strings for ``CustomerService.list_accessible_customers``.
        fields: objects (e.g. ``SimpleNamespace(name=..., category=...)``) for
            ``GoogleAdsFieldService.search_google_ads_fields``.
        batch_size: if set, split rows into multiple stream batches (exercises pagination).

    Recorded mutations land in ``self.mutations`` (one dict per mutate_* call).
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
        self.mutations: list[dict] = []
        self.enums = _Enums()

    def get_service(self, name: str):
        if name == "GoogleAdsService":
            return _GoogleAdsService(self._rows, self._batch_size, self.mutations)
        if name == "CustomerService":
            return _CustomerService(self._customers)
        if name == "GoogleAdsFieldService":
            return _FieldService(self._fields)
        # Any other service (CampaignService, AdGroupService, ...) is a mutate-capable entity service.
        return _MutateService(self.mutations)

    def get_type(self, type_name: str):
        if type_name in ("MutateOperation", "AdTextAsset"):
            return _NestedNamespace()
        return _Operation()
