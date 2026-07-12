"""Domain errors shared by registry and inference layers."""


class NoPromotedModelError(LookupError):
    """Raised when registry-backed inference has no champion model."""
