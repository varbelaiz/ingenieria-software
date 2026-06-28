"""Tests for MLflow registry helper behavior through an injected client."""

from ml.registry.client import MLflowRegistryClient


def test_register_run_model_creates_version_and_candidate_alias() -> None:
    """A run artifact should become a traceable candidate model version."""
    events: list[tuple[str, object]] = []

    class FakeModelVersion:
        version = "7"
        run_id = "run-123"
        source = "runs:/run-123/model/model.json"

    class FakeClient:
        def create_registered_model(self, name: str) -> None:
            events.append(("create_registered_model", name))

        def create_model_version(
            self, *, name: str, source: str, run_id: str
        ) -> FakeModelVersion:
            events.append(("create_model_version", (name, source, run_id)))
            return FakeModelVersion()

        def set_registered_model_alias(
            self, name: str, alias: str, version: str
        ) -> None:
            events.append(("set_alias", (name, alias, version)))

        def get_run(self, run_id: str) -> object:
            class Data:
                metrics = {"mae": 4.0}

            class Run:
                data = Data()

            return Run()

    registry = MLflowRegistryClient(client=FakeClient(), model_name="gas-forecast")

    model = registry.register_run_model("run-123")

    assert model.version == "7"
    assert model.run_id == "run-123"
    assert model.alias == "candidate"
    assert events[-1] == ("set_alias", ("gas-forecast", "candidate", "7"))
