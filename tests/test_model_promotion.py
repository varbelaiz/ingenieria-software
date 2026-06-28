"""Tests for metric-gated candidate-to-champion promotion."""

from ml.registry.client import RegisteredModel
from ml.registry.promote import register_and_promote
from ml.registry.promotion import PromotionPolicy, promote_candidate


def _model(version: str, mae: float | None, alias: str) -> RegisteredModel:
    metrics = {} if mae is None else {"mae": mae}
    return RegisteredModel(
        name="gas-forecast",
        version=version,
        run_id=f"run-{version}",
        alias=alias,
        metrics=metrics,
    )


class FakeRegistry:
    """In-memory registry surface used to observe alias changes."""

    def __init__(self, champion: RegisteredModel | None) -> None:
        """Initialize the fake with an optional current champion."""
        self.champion = champion
        self.promoted_versions: list[str] = []

    def get_champion(self) -> RegisteredModel | None:
        """Return the configured champion."""
        return self.champion

    def set_champion(self, version: str) -> None:
        """Record the version selected for promotion."""
        self.promoted_versions.append(version)


def test_candidate_below_threshold_and_better_than_champion_is_promoted() -> None:
    """A qualifying candidate should replace the current champion."""
    registry = FakeRegistry(champion=_model("1", 12.0, "champion"))

    decision = promote_candidate(
        registry,
        _model("2", 8.0, "candidate"),
        policy=PromotionPolicy(max_mae=10.0),
    )

    assert decision.status == "promoted"
    assert registry.promoted_versions == ["2"]


def test_rejected_candidate_does_not_replace_champion() -> None:
    """A worse candidate should leave the current champion unchanged."""
    registry = FakeRegistry(champion=_model("1", 7.0, "champion"))

    decision = promote_candidate(
        registry,
        _model("2", 8.0, "candidate"),
        policy=PromotionPolicy(max_mae=10.0),
    )

    assert decision.status == "rejected"
    assert decision.reason == "candidate does not improve champion MAE"
    assert not registry.promoted_versions


def test_candidate_without_mae_is_rejected() -> None:
    """A candidate without the required metric should be rejected."""
    registry = FakeRegistry(champion=None)

    decision = promote_candidate(
        registry,
        _model("2", None, "candidate"),
        policy=PromotionPolicy(max_mae=10.0),
    )

    assert decision.status == "rejected"
    assert decision.reason == "candidate is missing MAE"
    assert not registry.promoted_versions


def test_register_and_promote_evaluates_the_new_candidate() -> None:
    """The entrypoint should evaluate the version registered from the run."""
    candidate = _model("3", 6.0, "candidate")

    class Registry(FakeRegistry):
        """Fake registry that returns the newly registered candidate."""

        def register_run_model(self, run_id: str) -> RegisteredModel:
            """Return the candidate associated with the expected run."""
            assert run_id == "run-3"
            return candidate

    registry = Registry(champion=_model("1", 7.0, "champion"))

    decision = register_and_promote(
        registry,
        run_id="run-3",
        max_mae=10.0,
    )

    assert decision.status == "promoted"
    assert registry.promoted_versions == ["3"]
