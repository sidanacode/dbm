"""Provider registration, alias resolution, and capability enforcement."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from dbm_coordinator.providers.models import (
    ProviderKind,
    ProviderLifecycle,
    ProviderManifest,
)

ENTRY_POINT_GROUP = "dbm.providers.v1"


class ProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[ProviderKind, str], ProviderManifest] = {}
        self._aliases: dict[tuple[ProviderKind, str], str] = {}

    def register(self, manifest: ProviderManifest) -> None:
        canonical_key = (manifest.kind, manifest.id)
        if canonical_key in self._providers or canonical_key in self._aliases:
            raise ProviderError(
                "duplicate_provider",
                f"Provider identity {manifest.kind.value}/{manifest.id} is already registered.",
            )
        for alias in manifest.aliases:
            alias_key = (manifest.kind, alias)
            if alias_key in self._providers or alias_key in self._aliases:
                raise ProviderError(
                    "duplicate_provider_alias",
                    f"Provider alias {manifest.kind.value}/{alias} is already registered.",
                )
        self._providers[canonical_key] = manifest
        for alias in manifest.aliases:
            self._aliases[(manifest.kind, alias)] = manifest.id

    def resolve(self, kind: ProviderKind, provider_id: str) -> ProviderManifest:
        normalized = provider_id.strip().lower()
        canonical = self._aliases.get((kind, normalized), normalized)
        manifest = self._providers.get((kind, canonical))
        if manifest is None:
            raise ProviderError(
                "provider_unknown",
                f"Provider {kind.value}/{provider_id} is not registered.",
            )
        return manifest

    def require(self, kind: ProviderKind, provider_id: str, capability: str) -> ProviderManifest:
        manifest = self.resolve(kind, provider_id)
        if manifest.lifecycle == ProviderLifecycle.PLANNED:
            raise ProviderError(
                "provider_unavailable",
                f"Provider {kind.value}/{manifest.id} is planned but not available.",
            )
        if not manifest.supports(capability):
            raise ProviderError(
                "capability_unavailable",
                f"Provider {kind.value}/{manifest.id} does not provide {capability!r}.",
            )
        return manifest

    def manifests(self, kind: ProviderKind | None = None) -> list[ProviderManifest]:
        values = [
            manifest
            for (provider_kind, _), manifest in self._providers.items()
            if kind is None or provider_kind == kind
        ]
        return sorted(values, key=lambda item: (item.kind.value, item.id))

    def discover_plugins(self, plugins: Iterable[EntryPoint] | None = None) -> None:
        candidates = plugins if plugins is not None else entry_points(group=ENTRY_POINT_GROUP)
        for candidate in candidates:
            loaded: Any = candidate.load()
            if callable(loaded):
                loaded = loaded()
            if hasattr(loaded, "manifest"):
                loaded = loaded.manifest
            manifest = ProviderManifest.model_validate(loaded)
            self.register(manifest)
