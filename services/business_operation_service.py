from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError

from extensions import db
from models.business_operation import BusinessOperation


class OperationRequestConflict(ValueError):
    """Raised when an idempotency key is reused for a different request."""


class OperationInProgress(RuntimeError):
    """Raised when the existing operation has no reusable result yet."""


def request_fingerprint(payload: Any) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _replay_result(
    operation: BusinessOperation,
    expected_fingerprint: str,
):
    if operation.request_fingerprint != expected_fingerprint:
        raise OperationRequestConflict(
            "Idempotency key đã được dùng cho request không khớp."
        )
    if operation.status != "completed" or operation.result_snapshot is None:
        raise OperationInProgress("Thao tác cùng idempotency key đang được xử lý.")
    return operation.result_snapshot


def complete_operation(operation: BusinessOperation, result_snapshot: dict):
    operation.status = "completed"
    operation.result_snapshot = result_snapshot
    operation.completed_at = datetime.now()


def replay_operation(operation: BusinessOperation, request_payload: Any):
    return _replay_result(
        operation,
        request_fingerprint(request_payload),
    )


def execute_operation(
    *,
    hotel_id: int,
    operation_key: str,
    action: str,
    entity_type: str,
    entity_id: int,
    request_payload: Any,
    handler: Callable[[BusinessOperation], dict],
):
    """Execute a mutation once and replay its committed result on retry.

    The use-case owns the transaction. Callers must invoke it with a clean
    session and must not commit inside ``handler``.
    """
    fingerprint = request_fingerprint(request_payload)

    try:
        with db.session.begin():
            existing = (
                BusinessOperation.query.filter_by(
                    hotel_id=hotel_id,
                    operation_key=operation_key,
                )
                .with_for_update()
                .first()
            )
            if existing is not None:
                return _replay_result(existing, fingerprint), True

            operation = BusinessOperation(
                hotel_id=hotel_id,
                operation_key=operation_key,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                status="processing",
                request_fingerprint=fingerprint,
            )
            db.session.add(operation)
            db.session.flush()

            result = handler(operation)
            if not isinstance(result, dict):
                raise TypeError("Operation handler phải trả về dict JSON.")
            complete_operation(operation, result)
            db.session.flush()

        return result, False
    except IntegrityError as original_error:
        db.session.rollback()
        with db.session.begin():
            existing = (
                BusinessOperation.query.filter_by(
                    hotel_id=hotel_id,
                    operation_key=operation_key,
                )
                .with_for_update()
                .first()
            )
            if existing is None:
                raise original_error
            return _replay_result(existing, fingerprint), True
