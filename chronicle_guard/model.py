from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def scope_key(workflow_id: str, entity_id: str) -> str:
    """Return a stable, unambiguous key for workflow-owned state."""
    return f"{len(workflow_id)}:{workflow_id}:{entity_id}"


class EventKind(StrEnum):
    ACTION_REQUESTED = "action_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REVOKED = "approval_revoked"
    ACTION_EXECUTED = "action_executed"
    EVIDENCE_RECORDED = "evidence_recorded"
    TOOL_TIMEOUT = "tool_timeout"
    UNTRUSTED_INSTRUCTION = "untrusted_instruction"
    ACTION_CANCELLED = "action_cancelled"
    RING_EVENT = "ring_event"


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    kind: EventKind
    at: int = Field(ge=0)
    action_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    workflow_id: str = "wf-demo"
    source: str = "simulator"
    event_time: int | None = Field(default=None, ge=0)
    processing_time: int | None = Field(default=None, ge=0)
    sequence: int | None = Field(default=None, ge=0)
    correlation_id: str = "corr-demo"
    entity_id: str | None = None
    provenance: str = "simulated"
    state_outcome: str | None = None
    approval_id: str | None = None
    evidence_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def logical_time(self) -> int:
        """Event time is authoritative; ``at`` remains a compact compatibility field."""
        return self.event_time if self.event_time is not None else self.at

    @property
    def received_time(self) -> int:
        """Processing time defaults to event time in deterministic fixtures."""
        return self.processing_time if self.processing_time is not None else self.at


class Approval(BaseModel):
    workflow_id: str = Field(default="wf-demo", min_length=1)
    approval_id: str
    action_id: str
    actor: str
    granted_at: int
    revoked_at: int | None = None


class ActionRecord(BaseModel):
    workflow_id: str = "wf-demo"
    action_id: str
    requested_at: int
    requested_by: str
    executed_at: int | None = None
    executed_by: str | None = None
    execution_event_id: str | None = None
    cancelled_at: int | None = None
    cancelled_by: str | None = None
    cancellation_event_id: str | None = None


class EvidenceRecord(BaseModel):
    workflow_id: str = "wf-demo"
    evidence_id: str
    action_id: str
    recorded_at: int
    source: str
    approval_id: str | None = None


class GuardState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clock: int = 0
    actions: dict[str, ActionRecord] = Field(default_factory=dict)
    approvals: dict[str, Approval] = Field(default_factory=dict)
    evidence: dict[str, EvidenceRecord] = Field(default_factory=dict)
    applied_event_ids: list[str] = Field(default_factory=list)
    ignored_duplicate_ids: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    allowed: bool
    action_id: str
    reasons: list[str] = Field(default_factory=list)
    approval_id: str | None = None


class Violation(BaseModel):
    code: str
    event_id: str | None = None
    action_id: str | None = None
    message: str


class VerificationResult(BaseModel):
    valid: bool
    violations: list[Violation] = Field(default_factory=list)
    checked_event_ids: list[str] = Field(default_factory=list)
    first_violation_event_id: str | None = None
    verifier_version: str = "0.3.0"


class ReplayRequest(BaseModel):
    events: list[Event] = Field(default_factory=list)


class ActionRequest(BaseModel):
    events: list[Event] = Field(default_factory=list)
    action_id: str | None = None


class RepairRequest(BaseModel):
    events: list[Event] = Field(default_factory=list)
    drop_event_ids: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    events: list[Event] = Field(default_factory=list)
    include_state: bool = True


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RepairDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]


class ScenarioRun(BaseModel):
    name: str
    description: str
    events: list[Event]
    scenario_id: str | None = None
    version: str = "1.0"
    seed: int = 7
    policy_version: str = "baseline-v1"
    initial_state: dict[str, Any] = Field(default_factory=dict)
