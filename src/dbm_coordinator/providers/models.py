"""Versioned, serializable contracts for integration providers."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderKind(StrEnum):
    DATABASE = "database"
    SOURCE_CONTROL = "source_control"
    CI = "ci"
    MIGRATION = "migration"


class ProviderLifecycle(StrEnum):
    AVAILABLE = "available"
    PREVIEW = "preview"
    PLANNED = "planned"


class ProviderManifest(BaseModel):
    """Capabilities exposed by one provider adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: int = Field(default=1, ge=1, le=1)
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    kind: ProviderKind
    display_name: str = Field(min_length=1, max_length=100)
    adapter_version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    lifecycle: ProviderLifecycle
    capabilities: tuple[str, ...] = ()
    planned_capabilities: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_sets(self) -> "ProviderManifest":
        values = (*self.capabilities, *self.planned_capabilities, *self.aliases)
        if any(not value or value != value.lower() for value in values):
            raise ValueError("Capabilities and aliases must be non-empty lowercase values.")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("Capabilities must be unique.")
        if len(self.planned_capabilities) != len(set(self.planned_capabilities)):
            raise ValueError("Planned capabilities must be unique.")
        if set(self.capabilities) & set(self.planned_capabilities):
            raise ValueError("A capability cannot be both available and planned.")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("Aliases must be unique.")
        if self.id in self.aliases:
            raise ValueError("A provider ID cannot also be its alias.")
        if self.lifecycle == ProviderLifecycle.PLANNED and self.capabilities:
            raise ValueError("A planned provider cannot advertise available capabilities.")
        return self

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities
