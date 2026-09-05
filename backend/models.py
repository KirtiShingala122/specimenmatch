"""
models.py — SQLAlchemy ORM models for SpecimenMatch.

Four core entities:
  - Hospital      : An institution that holds patient records.
  - Patient       : A patient record as stored by a specific hospital.
  - LabResult     : An incoming lab result with raw (unparsed) demographics.
  - ResolutionDecision : The outcome of a single identity-resolution attempt.

Design decisions:
  - No SSN or real-world sensitive identifiers (per privacy requirement).
  - Raw lab demographics are stored as JSON to preserve the original data.
  - evidence_breakdown is stored as JSON so the scorer can emit any structure.
  - All primary keys are UUIDs (stored as strings in SQLite).
  - Timestamps are UTC-aware ISO strings stored as Text (SQLite has no
    native TIMESTAMP WITH TIMEZONE; Text avoids silent conversion bugs).
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    DateTime,
)
from sqlalchemy.orm import relationship
import enum

from backend.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GenderEnum(str, enum.Enum):
    M = "M"
    F = "F"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class OutcomeEnum(str, enum.Enum):
    MATCH = "MATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_MATCH = "NO_MATCH"


class TriggeredByEnum(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Hospital(Base):
    """
    Represents an institution (e.g. City General Hospital) that sends
    specimens to the shared external laboratory.
    """
    __tablename__ = "hospitals"

    hospital_id: str = Column(
        String(36), primary_key=True, default=_new_uuid
    )
    hospital_name: str = Column(String(255), nullable=False, unique=True)
    created_at: datetime = Column(DateTime, default=_utcnow, nullable=False)

    # Relationships
    patients: list["Patient"] = relationship(
        "Patient", back_populates="hospital", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Hospital id={self.hospital_id!r} name={self.hospital_name!r}>"


class Patient(Base):
    """
    A patient record as held by a specific hospital.

    Note: The same real-world person may appear as distinct Patient rows
    in different hospitals (cross-institution identity resolution is out
    of MVP scope). Each row is the authoritative record for that hospital.

    No SSN or sensitive national identifier is stored.
    """
    __tablename__ = "patients"

    patient_id: str = Column(
        String(36), primary_key=True, default=_new_uuid
    )
    hospital_id: str = Column(
        String(36), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    # Hospital-local Medical Record Number — unique within a hospital
    mrn: str = Column(String(64), nullable=False)

    # Core demographics
    first_name: str = Column(String(128), nullable=False)
    last_name: str = Column(String(128), nullable=False)
    middle_name: Optional[str] = Column(String(128), nullable=True)
    date_of_birth: datetime = Column(Date, nullable=False)
    gender: GenderEnum = Column(
        Enum(GenderEnum, name="gender_enum"), nullable=False, default=GenderEnum.UNKNOWN
    )

    # Contact / address (all nullable — real records are often incomplete)
    phone: Optional[str] = Column(String(32), nullable=True)
    address_line1: Optional[str] = Column(String(255), nullable=True)
    address_line2: Optional[str] = Column(String(255), nullable=True)
    city: Optional[str] = Column(String(128), nullable=True)
    state: Optional[str] = Column(String(64), nullable=True)
    zip_code: Optional[str] = Column(String(16), nullable=True)

    created_at: datetime = Column(DateTime, default=_utcnow, nullable=False)

    # Relationships
    hospital: "Hospital" = relationship("Hospital", back_populates="patients")
    resolution_decisions: list["ResolutionDecision"] = relationship(
        "ResolutionDecision", back_populates="matched_patient"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Patient id={self.patient_id!r} "
            f"name={self.first_name!r} {self.last_name!r} "
            f"dob={self.date_of_birth!r}>"
        )


class LabResult(Base):
    """
    An incoming lab result as submitted by the external laboratory.

    The raw_demographics column preserves the original data exactly as
    received (before normalization). The matching engine normalizes this
    internally and never overwrites raw_demographics.

    result_data holds the actual test result payload (opaque for matching).
    """
    __tablename__ = "lab_results"

    lab_result_id: str = Column(
        String(36), primary_key=True, default=_new_uuid
    )
    # The lab's internal barcode / accession number
    specimen_id: str = Column(String(128), nullable=False, unique=True, index=True)
    lab_name: str = Column(String(255), nullable=False)
    submitted_at: datetime = Column(DateTime, default=_utcnow, nullable=False)

    # Raw demographic fields as received from the lab — stored as-is
    # Expected keys (all optional from the lab's side):
    #   first_name, last_name, middle_name, date_of_birth,
    #   gender, phone, address
    raw_demographics: dict = Column(JSON, nullable=False)

    # The actual test result payload — opaque for identity matching
    result_data: dict = Column(JSON, nullable=True)

    # Relationships
    resolution_decisions: list["ResolutionDecision"] = relationship(
        "ResolutionDecision", back_populates="lab_result", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<LabResult id={self.lab_result_id!r} "
            f"specimen={self.specimen_id!r} lab={self.lab_name!r}>"
        )


class ResolutionDecision(Base):
    """
    The immutable audit record of a single identity-resolution attempt.

    An attempt is recorded every time the matching engine runs against a
    LabResult, whether triggered automatically on ingestion or manually
    by a reviewer.

    Outcomes:
      MATCH           — sufficient evidence for safe automatic assignment.
      REVIEW_REQUIRED — ambiguity detected; human review is required.
      NO_MATCH        — no candidate meets the minimum plausibility threshold.

    The evidence_breakdown column stores per-field similarity scores and
    notes so the UI can render a full explanation without re-running the
    matching engine.
    """
    __tablename__ = "resolution_decisions"

    decision_id: str = Column(
        String(36), primary_key=True, default=_new_uuid
    )
    lab_result_id: str = Column(
        String(36), ForeignKey("lab_results.lab_result_id"), nullable=False, index=True
    )
    resolved_at: datetime = Column(DateTime, default=_utcnow, nullable=False)

    # Outcome
    outcome: OutcomeEnum = Column(
        Enum(OutcomeEnum, name="outcome_enum"), nullable=False
    )

    # The patient record this result was matched to (null if REVIEW_REQUIRED / NO_MATCH)
    matched_patient_id: Optional[str] = Column(
        String(36), ForeignKey("patients.patient_id"), nullable=True, index=True
    )

    # Scoring metadata
    top_score: float = Column(Float, nullable=False)
    second_score: Optional[float] = Column(Float, nullable=True)
    score_margin: Optional[float] = Column(Float, nullable=True)
    candidate_count: int = Column(Integer, nullable=False, default=0)

    # Full field-by-field breakdown produced by the scorer
    # Example structure:
    # {
    #   "fields": {
    #     "last_name":  {"score": 1.0, "note": "exact match after normalization"},
    #     "first_name": {"score": 0.85, "note": "abbreviated: 'R.' vs 'Rahul'"},
    #     "dob":        {"score": 1.0, "note": "format difference: YYYY-MM-DD vs DD-MM-YYYY"},
    #     "gender":     {"score": 1.0, "note": "exact match"},
    #     "phone":      {"score": 1.0, "note": "match after stripping formatting"},
    #   },
    #   "top_candidates": [
    #     {"patient_id": "...", "name": "...", "score": 0.97},
    #     {"patient_id": "...", "name": "...", "score": 0.43},
    #   ]
    # }
    evidence_breakdown: dict = Column(JSON, nullable=False, default=dict)

    # Human-readable explanation of the decision
    decision_reason: str = Column(Text, nullable=False)

    # How the resolution was initiated
    triggered_by: TriggeredByEnum = Column(
        Enum(TriggeredByEnum, name="triggered_by_enum"),
        nullable=False,
        default=TriggeredByEnum.AUTO,
    )

    # Relationships
    lab_result: "LabResult" = relationship(
        "LabResult", back_populates="resolution_decisions"
    )
    matched_patient: Optional["Patient"] = relationship(
        "Patient", back_populates="resolution_decisions"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ResolutionDecision id={self.decision_id!r} "
            f"outcome={self.outcome!r} score={self.top_score!r}>"
        )
