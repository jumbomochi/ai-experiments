"""Stop running Compute Engine instances when the configured budget is exhausted."""

from __future__ import annotations

import base64
import binascii
import json
import os
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


def decode_budget_event(cloud_event: Mapping[str, object]) -> dict[str, object]:
    """Decode the JSON budget payload carried by a Pub/Sub CloudEvent."""
    try:
        event_data = getattr(cloud_event, "data", None)
        if event_data is None:
            event_data = cloud_event["data"]
        message = event_data["message"]  # type: ignore[index]
        encoded_payload = message["data"]
        decoded_payload = base64.b64decode(encoded_payload, validate=True)
        payload = json.loads(decoded_payload.decode("utf-8"))
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        UnicodeError,
    ) as exc:
        raise ValueError("invalid budget event") from exc

    if not isinstance(payload, dict):
        raise ValueError("invalid budget event")
    return payload


def _receipt(
    *,
    action: str,
    project_id: str,
    cost: Decimal,
    budget: Decimal,
) -> dict[str, object]:
    return {
        "action": action,
        "project_id": project_id,
        "cost_amount": str(cost),
        "budget_amount": str(budget),
        "stopped": [],
        "skipped": [],
        "failures": [],
    }


def handle_budget(
    payload: Mapping[str, object],
    *,
    expected_budget_name: str,
    expected_project_id: str,
    runtime_project_id: str,
    instances_client: Any,
) -> dict[str, object]:
    """Validate a budget payload and stop each running instance in the target project."""
    if payload["budgetDisplayName"] != expected_budget_name:
        raise ValueError("unexpected budget display name")
    if runtime_project_id != expected_project_id:
        raise RuntimeError("runtime project does not match configured project")
    try:
        cost = Decimal(str(payload["costAmount"]))
        budget = Decimal(str(payload["budgetAmount"]))
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise ValueError("payload must contain numeric amounts") from exc
    if not cost.is_finite() or not budget.is_finite():
        raise ValueError("payload must contain numeric amounts")
    if budget <= 0:
        raise ValueError("budget amount must be positive")
    if cost < budget:
        return _receipt(
            action="none",
            project_id=expected_project_id,
            cost=cost,
            budget=budget,
        )

    receipt = _receipt(
        action="stop",
        project_id=expected_project_id,
        cost=cost,
        budget=budget,
    )
    stopped = receipt["stopped"]
    skipped = receipt["skipped"]
    failures = receipt["failures"]

    for aggregate_key, scoped_instances in instances_client.aggregated_list(
        project=expected_project_id
    ):
        zone = aggregate_key.rsplit("/", maxsplit=1)[-1]
        for instance in getattr(scoped_instances, "instances", None) or []:
            instance_ref = f"{zone}/{instance.name}"
            if instance.status != "RUNNING":
                skipped.append({"instance": instance_ref, "status": instance.status})
                continue

            try:
                operation = instances_client.stop(
                    project=expected_project_id,
                    zone=zone,
                    instance=instance.name,
                )
                operation.result(timeout=300)
            except Exception as exc:  # A failed instance must not block the remaining stops.
                failures.append({"instance": instance_ref, "error": str(exc)})
            else:
                stopped.append(instance_ref)

    return receipt


def stop_compute_on_budget(cloud_event: Mapping[str, object]) -> dict[str, object]:
    """Cloud Run function entry point for budget Pub/Sub notifications."""
    expected_project_id = os.environ["EXPECTED_PROJECT_ID"]
    runtime_project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    expected_budget_name = os.environ["EXPECTED_BUDGET_NAME"]
    payload = decode_budget_event(cloud_event)

    from google.cloud import compute_v1

    receipt = handle_budget(
        payload,
        expected_budget_name=expected_budget_name,
        expected_project_id=expected_project_id,
        runtime_project_id=runtime_project_id,
        instances_client=compute_v1.InstancesClient(),
    )
    print(json.dumps(receipt))
    return receipt
