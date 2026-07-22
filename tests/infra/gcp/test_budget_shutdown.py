import base64
import json
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

from infra.gcp.project_controls.function.main import decode_budget_event, handle_budget
from infra.gcp.project_controls.function import main as budget_shutdown


PROJECT_ID = "sgcc-ai-experiments"
BUDGET_NAME = "ai-experiments-monthly"


class FakeOperation:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.timeouts: list[int] = []

    def result(self, *, timeout: int) -> None:
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error


class FakeInstancesClient:
    def __init__(
        self,
        instances_by_zone: dict[str, list[tuple[str, str]]],
        *,
        failures: set[tuple[str, str]] | None = None,
    ) -> None:
        self.instances_by_zone = instances_by_zone
        self.failures = failures or set()
        self.aggregated_list_calls: list[str] = []
        self.stop_calls: list[tuple[str, str, str]] = []
        self.operations: list[FakeOperation] = []

    def aggregated_list(self, *, project: str):
        self.aggregated_list_calls.append(project)
        return [
            (
                f"zones/{zone}",
                SimpleNamespace(
                    instances=[
                        SimpleNamespace(name=name, status=status) for name, status in instances
                    ]
                ),
            )
            for zone, instances in self.instances_by_zone.items()
        ]

    def stop(self, *, project: str, zone: str, instance: str) -> FakeOperation:
        self.stop_calls.append((project, zone, instance))
        error = RuntimeError("stop failed") if (zone, instance) in self.failures else None
        operation = FakeOperation(error)
        self.operations.append(operation)
        return operation


def payload(cost: object = 100, budget: object = 100) -> dict[str, object]:
    return {
        "budgetDisplayName": BUDGET_NAME,
        "costAmount": cost,
        "budgetAmount": budget,
    }


def run_handler(
    client: FakeInstancesClient, event_payload: dict[str, object] | None = None
) -> dict[str, object]:
    return handle_budget(
        event_payload or payload(),
        expected_budget_name=BUDGET_NAME,
        expected_project_id=PROJECT_ID,
        runtime_project_id=PROJECT_ID,
        instances_client=client,
    )


def encoded_event(event_payload: object) -> dict[str, object]:
    encoded = base64.b64encode(json.dumps(event_payload).encode()).decode()
    return {"data": {"message": {"data": encoded}}}


def test_cost_below_budget_returns_no_action_without_listing_or_stopping() -> None:
    client = FakeInstancesClient({"asia-southeast1-b": [("gpu", "RUNNING")]})

    receipt = run_handler(client, payload(cost="99.99"))

    assert receipt == {
        "action": "none",
        "project_id": PROJECT_ID,
        "cost_amount": "99.99",
        "budget_amount": "100",
        "stopped": [],
        "skipped": [],
        "failures": [],
    }
    assert client.aggregated_list_calls == []
    assert client.stop_calls == []


@pytest.mark.parametrize("cost", [100, "100.01"])
def test_cost_at_or_above_budget_stops_running_instances_across_zones(cost: object) -> None:
    client = FakeInstancesClient(
        {
            "asia-southeast1-b": [("gpu-a", "RUNNING")],
            "us-central1-a": [("gpu-b", "RUNNING")],
        }
    )

    receipt = run_handler(client, payload(cost=cost))

    assert receipt["action"] == "stop"
    assert receipt["stopped"] == ["asia-southeast1-b/gpu-a", "us-central1-a/gpu-b"]
    assert receipt["skipped"] == []
    assert receipt["failures"] == []
    assert client.aggregated_list_calls == [PROJECT_ID]
    assert client.stop_calls == [
        (PROJECT_ID, "asia-southeast1-b", "gpu-a"),
        (PROJECT_ID, "us-central1-a", "gpu-b"),
    ]
    assert [operation.timeouts for operation in client.operations] == [[300], [300]]


def test_non_running_instances_are_skipped() -> None:
    client = FakeInstancesClient(
        {
            "asia-southeast1-b": [
                ("done", "TERMINATED"),
                ("stopping", "STOPPING"),
                ("sleeping", "SUSPENDED"),
            ]
        }
    )

    receipt = run_handler(client)

    assert receipt["action"] == "stop"
    assert receipt["stopped"] == []
    assert receipt["skipped"] == [
        {"instance": "asia-southeast1-b/done", "status": "TERMINATED"},
        {"instance": "asia-southeast1-b/stopping", "status": "STOPPING"},
        {"instance": "asia-southeast1-b/sleeping", "status": "SUSPENDED"},
    ]
    assert receipt["failures"] == []
    assert client.stop_calls == []


def test_duplicate_delivery_after_instances_stop_is_successful_noop() -> None:
    client = FakeInstancesClient({"asia-southeast1-b": [("gpu", "RUNNING")]})

    first_receipt = run_handler(client)
    client.instances_by_zone["asia-southeast1-b"] = [("gpu", "TERMINATED")]
    second_receipt = run_handler(client)

    assert first_receipt["stopped"] == ["asia-southeast1-b/gpu"]
    assert second_receipt["action"] == "stop"
    assert second_receipt["stopped"] == []
    assert second_receipt["skipped"] == [
        {"instance": "asia-southeast1-b/gpu", "status": "TERMINATED"}
    ]
    assert second_receipt["failures"] == []
    assert client.stop_calls == [(PROJECT_ID, "asia-southeast1-b", "gpu")]


def test_one_stop_failure_is_recorded_without_preventing_other_stops() -> None:
    client = FakeInstancesClient(
        {
            "asia-southeast1-b": [
                ("bad", "RUNNING"),
                ("good", "RUNNING"),
            ]
        },
        failures={("asia-southeast1-b", "bad")},
    )

    receipt = run_handler(client)

    assert client.stop_calls == [
        (PROJECT_ID, "asia-southeast1-b", "bad"),
        (PROJECT_ID, "asia-southeast1-b", "good"),
    ]
    assert receipt["stopped"] == ["asia-southeast1-b/good"]
    assert receipt["failures"] == [
        {"instance": "asia-southeast1-b/bad", "error": "stop failed"}
    ]


@pytest.mark.parametrize(
    ("event", "match"),
    [
        ({"data": {"message": {"data": "%%%"}}}, "invalid budget event"),
        (
            {"data": {"message": {"data": base64.b64encode(b"not-json").decode()}}},
            "invalid budget event",
        ),
    ],
)
def test_decode_budget_event_rejects_malformed_messages(
    event: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        decode_budget_event(event)


def test_decode_budget_event_returns_json_payload() -> None:
    event_payload = payload(cost=125.5)

    assert decode_budget_event(encoded_event(event_payload)) == event_payload


@pytest.mark.parametrize(
    ("event_payload", "match"),
    [
        ({"budgetDisplayName": BUDGET_NAME, "budgetAmount": 100}, "numeric amounts"),
        ({"budgetDisplayName": BUDGET_NAME, "costAmount": 100}, "numeric amounts"),
        (payload(cost="not-a-number"), "numeric amounts"),
        (payload(budget=0), "budget amount must be positive"),
        (payload(budget=-1), "budget amount must be positive"),
        (
            {**payload(), "budgetDisplayName": "some-other-budget"},
            "unexpected budget display name",
        ),
    ],
)
def test_invalid_payload_is_rejected_before_mutation(
    event_payload: dict[str, object], match: str
) -> None:
    client = FakeInstancesClient({"asia-southeast1-b": [("gpu", "RUNNING")]})

    with pytest.raises(ValueError, match=match):
        run_handler(client, event_payload)

    assert client.aggregated_list_calls == []
    assert client.stop_calls == []


def test_runtime_project_mismatch_is_rejected_before_listing() -> None:
    client = FakeInstancesClient({"asia-southeast1-b": [("gpu", "RUNNING")]})

    with pytest.raises(RuntimeError, match="runtime project does not match configured project"):
        handle_budget(
            payload(),
            expected_budget_name=BUDGET_NAME,
            expected_project_id=PROJECT_ID,
            runtime_project_id="adept-prod-497323",
            instances_client=client,
        )

    assert client.aggregated_list_calls == []
    assert client.stop_calls == []


def test_cloud_run_entrypoint_uses_lazy_compute_client_and_prints_receipt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeInstancesClient({"asia-southeast1-b": [("gpu", "RUNNING")]})
    compute_module = ModuleType("google.cloud.compute_v1")
    compute_module.InstancesClient = lambda: client  # type: ignore[attr-defined]
    cloud_module = ModuleType("google.cloud")
    cloud_module.compute_v1 = compute_module  # type: ignore[attr-defined]
    google_module = ModuleType("google")
    google_module.cloud = cloud_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setitem(sys.modules, "google.cloud.compute_v1", compute_module)
    monkeypatch.setenv("EXPECTED_PROJECT_ID", PROJECT_ID)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", PROJECT_ID)
    monkeypatch.setenv("EXPECTED_BUDGET_NAME", BUDGET_NAME)
    cloud_event = SimpleNamespace(data=encoded_event(payload())["data"])

    receipt = budget_shutdown.stop_compute_on_budget(cloud_event)

    assert receipt["stopped"] == ["asia-southeast1-b/gpu"]
    assert json.loads(capsys.readouterr().out) == receipt
