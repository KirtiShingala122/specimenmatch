import uuid
import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Date, Enum, Float, ForeignKey, Integer, JSON, String, Text, DateTime
from sqlalchemy.orm import relationship

from backend.database import Base


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


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id = Column(String(36), primary_key=True, default=_new_uuid)
    hospital_name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    patients = relationship("Patient", back_populates="hospital", cascade="all, delete-orphan")


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(36), primary_key=True, default=_new_uuid)
    hospital_id = Column(String(36), ForeignKey("hospitals.hospital_id"), nullable=False, index=True)
    mrn = Column(String(64), nullable=False)

    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), nullable=True)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(GenderEnum, name="gender_enum"), nullable=False, default=GenderEnum.UNKNOWN)

    phone = Column(String(32), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(128), nullable=True)
    state = Column(String(64), nullable=True)
    zip_code = Column(String(16), nullable=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False)

    hospital = relationship("Hospital", back_populates="patients")
    resolution_decisions = relationship("ResolutionDecision", back_populates="matched_patient")


class LabResult(Base):
    __tablename__ = "lab_results"

    lab_result_id = Column(String(36), primary_key=True, default=_new_uuid)
    specimen_id = Column(String(128), nullable=False, unique=True, index=True)
    lab_name = Column(String(255), nullable=False)
    submitted_at = Column(DateTime, default=_utcnow, nullable=False)

    # Stored as-is — normalization is the matching engine's job
    raw_demographics = Column(JSON, nullable=False)
    result_data = Column(JSON, nullable=True)

    resolution_decisions = relationship(
        "ResolutionDecision", back_populates="lab_result", cascade="all, delete-orphan"
    )


class ResolutionDecision(Base):
    """Immutable audit record of one identity-resolution attempt."""
    __tablename__ = "resolution_decisions"

    decision_id = Column(String(36), primary_key=True, default=_new_uuid)
    lab_result_id = Column(String(36), ForeignKey("lab_results.lab_result_id"), nullable=False, index=True)
    resolved_at = Column(DateTime, default=_utcnow, nullable=False)

    outcome = Column(Enum(OutcomeEnum, name="outcome_enum"), nullable=False)

    # Null for REVIEW_REQUIRED / NO_MATCH — never guess
    matched_patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=True, index=True)

    top_score = Column(Float, nullable=False)
    second_score = Column(Float, nullable=True)
    score_margin = Column(Float, nullable=True)
    candidate_count = Column(Integer, nullable=False, default=0)

    # Per-field scores + top candidates — rendered directly by the UI
    evidence_breakdown = Column(JSON, nullable=False, default=dict)
    decision_reason = Column(Text, nullable=False)

    triggered_by = Column(
        Enum(TriggeredByEnum, name="triggered_by_enum"),
        nullable=False,
        default=TriggeredByEnum.AUTO,
    )

    lab_result = relationship("LabResult", back_populates="resolution_decisions")
    matched_patient = relationship("Patient", back_populates="resolution_decisions")
