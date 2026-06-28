"""Metric-gated candidate promotion for MLflow model aliases."""

from dataclasses import dataclass
from typing import Literal, Protocol

from ml.registry.client import RegisteredModel


class PromotionRegistry(Protocol):
    """Registry operations needed by the promotion policy."""

    def get_champion(self) -> RegisteredModel | None:
        """Return the current champion, when one exists."""

    def set_champion(self, version: str) -> None:
        """Move the champion alias to a model version."""


@dataclass(frozen=True)
class PromotionPolicy:
    """Minimum model-quality requirements."""

    max_mae: float


@dataclass(frozen=True)
class PromotionDecision:
    """Auditable outcome for one candidate evaluation."""

    status: Literal["promoted", "rejected"]
    reason: str
    version: str


def promote_candidate(
    registry: PromotionRegistry,
    candidate: RegisteredModel,
    *,
    policy: PromotionPolicy,
) -> PromotionDecision:
    """Promote only candidates with valid MAE that improve the champion."""

    candidate_mae = candidate.metrics.get("mae")
    if candidate_mae is None:
        return PromotionDecision(
            status="rejected",
            reason="candidate is missing MAE",
            version=candidate.version,
        )
    if candidate_mae > policy.max_mae:
        return PromotionDecision(
            status="rejected",
            reason="candidate MAE exceeds promotion threshold",
            version=candidate.version,
        )

    champion = registry.get_champion()
    if champion is not None:
        champion_mae = champion.metrics.get("mae")
        if champion_mae is not None and candidate_mae >= champion_mae:
            return PromotionDecision(
                status="rejected",
                reason="candidate does not improve champion MAE",
                version=candidate.version,
            )

    registry.set_champion(candidate.version)
    return PromotionDecision(
        status="promoted",
        reason="candidate satisfies promotion policy",
        version=candidate.version,
    )
