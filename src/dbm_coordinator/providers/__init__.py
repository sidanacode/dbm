"""Provider manifests and registry for DBM integrations."""

from dbm_coordinator.providers.builtins import builtin_manifests
from dbm_coordinator.providers.models import (
    ProviderKind,
    ProviderLifecycle,
    ProviderManifest,
)
from dbm_coordinator.providers.registry import ProviderError, ProviderRegistry


def create_provider_registry(*, discover_plugins: bool = False) -> ProviderRegistry:
    """Create a registry containing built-ins and optional installed plugins."""
    registry = ProviderRegistry()
    for manifest in builtin_manifests():
        registry.register(manifest)
    if discover_plugins:
        registry.discover_plugins()
    return registry


__all__ = [
    "ProviderError",
    "ProviderKind",
    "ProviderLifecycle",
    "ProviderManifest",
    "ProviderRegistry",
    "create_provider_registry",
]
