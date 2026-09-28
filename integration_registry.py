from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .integrations import (
    google_calendar_status,
    imap_status,
    notion_status,
    sync_google_calendar,
    sync_notion,
)


StatusFn = Callable[[Any], dict[str, Any]]
SyncFn = Callable[[Any, list[dict[str, Any]], dict[str, Any]], dict[str, Any]]
EligibilityFn = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class IntegrationAdapter:
    key: str
    label: str
    direction: str
    status_fn: StatusFn
    document_sync_fn: SyncFn | None = None
    eligibility_fn: EligibilityFn | None = None
    supports_scope: bool = False
    idempotent: bool = False

    @property
    def supports_document_sync(self) -> bool:
        return self.document_sync_fn is not None

    def status(self, settings) -> dict[str, Any]:
        return self.status_fn(settings)

    def eligible_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.eligibility_fn:
            return list(documents)
        return [document for document in documents if self.eligibility_fn(document)]

    def sync_documents(
        self,
        settings,
        documents: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.document_sync_fn:
            raise RuntimeError(f"Integration {self.key} does not support document sync.")
        return self.document_sync_fn(settings, documents, options or {})

    def public_info(self, settings) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "direction": self.direction,
            "supports_scope": self.supports_scope,
            "supports_document_sync": self.supports_document_sync,
            "idempotent": self.idempotent,
            "status": self.status(settings),
        }


_ADAPTERS: dict[str, IntegrationAdapter] = {}


def register_integration_adapter(adapter: IntegrationAdapter, *, replace: bool = False) -> None:
    if adapter.key in _ADAPTERS and not replace:
        raise ValueError(f"Integration adapter already registered: {adapter.key}")
    _ADAPTERS[adapter.key] = adapter


def unregister_integration_adapter(key: str) -> None:
    _ADAPTERS.pop(key, None)


def get_integration_adapter(key: str) -> IntegrationAdapter | None:
    return _ADAPTERS.get(key)


def integration_catalog(settings) -> list[dict[str, Any]]:
    return [
        adapter.public_info(settings)
        for adapter in sorted(_ADAPTERS.values(), key=lambda item: item.key)
    ]


def _notion_sync(settings, documents: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    return sync_notion(settings, documents, limit=int(options.get("limit") or len(documents) or 1))


def _calendar_sync(settings, documents: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    return sync_google_calendar(
        settings,
        documents,
        calendar_id=str(options.get("calendar_id") or "primary"),
    )


def _calendar_eligible(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata") or {}
    return bool(metadata.get("deadline") or metadata.get("warranty_until"))


register_integration_adapter(
    IntegrationAdapter(
        key="email",
        label="Email",
        direction="import",
        status_fn=imap_status,
        supports_scope=False,
        idempotent=False,
    )
)
register_integration_adapter(
    IntegrationAdapter(
        key="notion",
        label="Notion",
        direction="export",
        status_fn=notion_status,
        document_sync_fn=_notion_sync,
        supports_scope=True,
        idempotent=True,
    )
)
register_integration_adapter(
    IntegrationAdapter(
        key="google_calendar",
        label="Google Calendar",
        direction="export",
        status_fn=google_calendar_status,
        document_sync_fn=_calendar_sync,
        eligibility_fn=_calendar_eligible,
        supports_scope=True,
        idempotent=True,
    )
)
