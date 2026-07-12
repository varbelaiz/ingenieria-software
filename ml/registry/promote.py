"""CLI for registering and conditionally promoting a training run."""

import argparse
import json
from typing import Protocol

from ml.registry.client import MLflowRegistryClient, RegisteredModel
from ml.registry.promotion import (
    PromotionDecision,
    PromotionPolicy,
    PromotionRegistry,
    promote_candidate,
)


class RegistrationPromotionRegistry(PromotionRegistry, Protocol):
    """Registry operations required by the promotion entrypoint."""

    def register_run_model(self, run_id: str) -> RegisteredModel:
        """Register one training run as the candidate version."""


def register_and_promote(
    registry: RegistrationPromotionRegistry,
    *,
    run_id: str,
    max_mae: float,
) -> PromotionDecision:
    """Register a run as candidate and evaluate it for champion promotion."""

    candidate = registry.register_run_model(run_id)
    return promote_candidate(
        registry,
        candidate,
        policy=PromotionPolicy(max_mae=max_mae),
    )


def main() -> None:
    """Run model registration and promotion from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-mae", type=float, default=100.0)
    args = parser.parse_args()

    decision = register_and_promote(
        MLflowRegistryClient(),
        run_id=args.run_id,
        max_mae=args.max_mae,
    )
    print(
        json.dumps(
            {
                "status": decision.status,
                "reason": decision.reason,
                "version": decision.version,
            }
        )
    )


if __name__ == "__main__":
    main()
