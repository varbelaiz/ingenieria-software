"""Tests for MLflow registry helper behavior through an injected client."""

from ml.registry.client import MLflowRegistryClient


def test_register_run_model_creates_version_and_candidate_alias() -> None:
    """A run artifact should become a traceable candidate model version."""
    events: list[tuple[str, object]] = []

    class FakeModelVersion:
        """Minimal MLflow model-version response."""

        version = "7"
        run_id = "run-123"
        source = "runs:/run-123/model/model.json"

    class FakeClient:
        """Capture MLflow registry operations."""

        def create_registered_model(self, name: str) -> None:
            """Capture registered-model creation."""
            events.append(("create_registered_model", name))

        def create_model_version(
            self, *, name: str, source: str, run_id: str
        ) -> FakeModelVersion:
            """Capture and return model-version creation."""
            events.append(("create_model_version", (name, source, run_id)))
            return FakeModelVersion()

        def set_registered_model_alias(
            self, name: str, alias: str, version: str
        ) -> None:
            """Capture alias assignment."""
            events.append(("set_alias", (name, alias, version)))

        def get_run(self, _run_id: str) -> object:
            """Return metrics associated with the registered run."""

            class Data:
                """Minimal MLflow run-data response."""

                metrics = {"mae": 4.0}

            class Run:
                """Minimal MLflow run response."""

                data = Data()

            return Run()

    registry = MLflowRegistryClient(client=FakeClient(), model_name="gas-forecast")

    model = registry.register_run_model("run-123")

    assert model.version == "7"
    assert model.run_id == "run-123"
    assert model.alias == "candidate"
    assert events[-1] == ("set_alias", ("gas-forecast", "candidate", "7"))
