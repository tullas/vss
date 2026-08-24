class ResourceContractError(ValueError):
    """A scoped resource value failed closed contract validation."""


class ResourceRegistryError(ResourceContractError):
    """The immutable scoped resource registry is invalid."""
