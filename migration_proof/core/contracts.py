"""Typed, runtime-validated contracts; no authority-bearing operations here."""
from dataclasses import dataclass
from typing import Literal
import re

Revision = Literal["original", "faulty", "corrected"]
CHECKS = ("manifest_integrity", "fixture_health", "baseline_tests", "tenant_boundary")
TOOL_VERSION = "1"


class Rejected(ValueError):
    """A request violated a deterministic precondition."""


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise Rejected("invalid run identifier")


def digest(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise Rejected("invalid SHA-256 digest")


def revision(value: str) -> None:
    if value not in ("original", "faulty", "corrected"):
        raise Rejected("unsupported immutable revision")


@dataclass(frozen=True)
class InspectInput:
    run_id: str
    version: Revision

    def __post_init__(self):
        identifier(self.run_id)
        revision(self.version)


@dataclass(frozen=True)
class BaselineInput:
    run_id: str
    digest: str

    def __post_init__(self):
        identifier(self.run_id)
        digest(self.digest)


@dataclass(frozen=True)
class CompareInput:
    run_id: str
    original_digest: str
    candidate_digest: str

    def __post_init__(self):
        identifier(self.run_id)
        digest(self.original_digest)
        digest(self.candidate_digest)


@dataclass(frozen=True)
class PatchInput:
    run_id: str
    digest: str
    patch: str

    def __post_init__(self):
        identifier(self.run_id)
        digest(self.digest)
        if not isinstance(self.patch, str) or len(self.patch.encode()) > 16000:
            raise Rejected("patch must be bounded UTF-8 text")


@dataclass(frozen=True)
class InspectOutput:
    run_id: str
    version: Revision
    original_digest: str
    candidate_digest: str
    routes: tuple[str, ...]
    healthy: bool
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class BaselineOutput:
    run_id: str
    digest: str
    command_id: str
    exit_status: int
    test_count: int
    duration_seconds: float
    result_hash: str
    evidence_id: str


@dataclass(frozen=True)
class CompareOutput:
    run_id: str
    candidate_digest: str
    passed: bool
    trials: tuple[dict, ...]
    result_hash: str
    evidence_id: str


@dataclass(frozen=True)
class PatchOutput:
    run_id: str
    previous_digest: str
    candidate_digest: str
    repair_id: str
    required_rerun: tuple[str, ...] = CHECKS
