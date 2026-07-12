"""Tests for reproducible, point-in-time training dataset construction."""

from datetime import date
from decimal import Decimal

import pytest

from ml.features.store import FeatureRow
from ml.training.dataset import InsufficientTrainingDataError, build_training_dataset


def _row(well_id: str, month: int, gas: str) -> FeatureRow:
    return FeatureRow(
        well_id=well_id,
        as_of_date=date(2024, month, 1),
        gas_production_current=Decimal(gas),
        gas_production_avg_3m=Decimal(gas),
        gas_production_avg_6m=Decimal(gas),
        gas_production_trend_3m=Decimal("0"),
        oil_production_current=Decimal("10"),
        water_production_current=Decimal("5"),
        producing_days_available=30,
        production_months_available=month,
        formation="Vaca Muerta",
        basin="Neuquina",
        resource_type="Shale",
    )


def test_build_training_dataset_is_reproducible_and_sorted() -> None:
    """The same cutoff should produce stable examples regardless of input order."""
    rows = [
        _row("POZO-002", 2, "70"),
        _row("POZO-001", 3, "80"),
        _row("POZO-001", 1, "100"),
        _row("POZO-002", 1, "75"),
        _row("POZO-001", 2, "90"),
    ]

    first = build_training_dataset(rows, as_of_date=date(2024, 3, 1))
    second = build_training_dataset(reversed(rows), as_of_date=date(2024, 3, 1))

    assert first == second
    assert first.features == ((100.0,), (90.0,), (75.0,))
    assert first.targets == (90.0, 80.0, 70.0)
    assert first.dataset_start == date(2024, 1, 1)
    assert first.dataset_end == date(2024, 3, 1)


def test_build_training_dataset_does_not_use_future_target() -> None:
    """A feature row must not be paired with a target beyond the cutoff."""
    rows = [
        _row("POZO-001", 1, "100"),
        _row("POZO-001", 2, "90"),
        _row("POZO-001", 3, "1"),
    ]

    dataset = build_training_dataset(rows, as_of_date=date(2024, 2, 15))

    assert dataset.features == ((100.0,),)
    assert dataset.targets == (90.0,)
    assert dataset.dataset_end == date(2024, 2, 1)


def test_build_training_dataset_rejects_rows_without_known_targets() -> None:
    """Training should fail clearly when no complete feature/target pair exists."""
    with pytest.raises(InsufficientTrainingDataError):
        build_training_dataset(
            [_row("POZO-001", 1, "100")],
            as_of_date=date(2024, 1, 31),
        )
