"""Point-in-time training dataset construction from persisted feature rows."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from ml.features.store import FeatureRepository, FeatureRow


class InsufficientTrainingDataError(ValueError):
    """Raised when a cutoff has no complete feature/target pairs."""


@dataclass(frozen=True)
class TrainingDataset:
    """Immutable numeric training matrix and its reproducibility metadata."""

    feature_names: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    targets: tuple[float, ...]
    dataset_start: date
    dataset_end: date
    as_of_date: date


def build_training_dataset(
    rows: Iterable[FeatureRow], *, as_of_date: date
) -> TrainingDataset:
    """Pair each monthly snapshot with its next known gas-production target."""

    history_by_well: dict[str, list[FeatureRow]] = defaultdict(list)
    for row in rows:
        if row.as_of_date <= as_of_date:
            history_by_well[row.well_id].append(row)

    examples: list[tuple[str, date, date, float, float]] = []
    for well_id, history in history_by_well.items():
        ordered = sorted(history, key=lambda row: row.as_of_date)
        for feature_row, target_row in zip(ordered, ordered[1:]):
            if target_row.as_of_date <= as_of_date:
                examples.append(
                    (
                        well_id,
                        feature_row.as_of_date,
                        target_row.as_of_date,
                        float(feature_row.gas_production_current),
                        float(target_row.gas_production_current),
                    )
                )

    if not examples:
        raise InsufficientTrainingDataError(
            f"No complete training examples at or before {as_of_date.isoformat()}"
        )

    examples.sort(key=lambda item: (item[0], item[1]))
    return TrainingDataset(
        feature_names=("gas_production_current",),
        features=tuple((item[3],) for item in examples),
        targets=tuple(item[4] for item in examples),
        dataset_start=min(item[1] for item in examples),
        dataset_end=max(item[2] for item in examples),
        as_of_date=as_of_date,
    )


def load_training_dataset(
    repository: FeatureRepository, *, as_of_date: date
) -> TrainingDataset:
    """Read persisted feature history and build a cutoff-safe dataset."""

    return build_training_dataset(
        repository.list_features(as_of_date),
        as_of_date=as_of_date,
    )
