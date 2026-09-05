"""
schemas.py — Pydantic v2 request/response schemas for SpecimenMatch.

Schemas are kept separate from SQLAlchemy models so the API contract
is explicitly defined and does not leak ORM internals.

Naming convention:
  <Entity>Base   — shared fields used in creation and reading
  <Entity>Create — fields accepted on POST (excludes server-generated fields)
  <Entity>Read   — full representation returned from the API

No SSN or real-world sensitive identifiers are included.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import GenderEnum, OutcomeEnum, TriggeredByEnum


# ---------------------------------------------------------------------------
# Hospital
# ---------------------------------------------------------------------------

class HospitalBase(BaseModel):
    hospital_name: str = Field(..., min_length=1, max_length=255)


class HospitalCreate(HospitalBase):
    """Fields accepted when registering a new hospital."""
    pass


class HospitalRead(HospitalBase):
    """Full hospital representation returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    hospital_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

class PatientBase(BaseModel):
    mrn: str = Field(..., min_length=1, max_length=64, description="Hospital-local Medical Record Number")
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    middle_name: Optional[str] = Field(None, max_length=128)
    date_of_birth: date
    gender: GenderEnum = GenderEnum.UNKNOWN
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=128)
    state: Optional[str] = Field(None, max_length=64)
    zip_code: Optional[str] = Field(None, max_length=16)


class PatientCreate(PatientBase):
    """Fields accepted when creating a patient record under a hospital."""
    hospital_id: str = Field(..., description="ID of the owning hospital")


class PatientRead(PatientBase):
    """Full patient representation returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    hospital_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Lab Result
# ---------------------------------------------------------------------------

class LabResultDemographics(BaseModel):
    """
    The demographic fields as supplied by the external lab.
    All fields are optional because labs may omit some fields, and we
    must preserve whatever they sent without enforcing our own schema.
    """
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    date_of_birth: Optional[str] = Field(
        None,
        description=(
            "DOB in any format the lab uses. Stored raw; "
            "normalization happens in the matching engine."
        ),
    )
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class LabResultBase(BaseModel):
    specimen_id: str = Field(..., min_length=1, max_length=128, description="Lab accession / barcode number")
    lab_name: str = Field(..., min_length=1, max_length=255)
    raw_demographics: LabResultDemographics
    result_data: Optional[dict[str, Any]] = Field(
        None, description="Opaque test result payload — not used for matching"
    )


class LabResultCreate(LabResultBase):
    """Fields accepted when submitting a new lab result."""
    pass


class LabResultRead(BaseModel):
    """Full lab result representation returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    lab_result_id: str
    specimen_id: str
    lab_name: str
    submitted_at: datetime
    raw_demographics: dict[str, Any]
    result_data: Optional[dict[str, Any]]


# ---------------------------------------------------------------------------
# Evidence breakdown sub-schemas (used inside ResolutionDecision)
# ---------------------------------------------------------------------------

class FieldEvidence(BaseModel):
    """Score and explanation for a single demographic field."""
    score: float = Field(..., ge=0.0, le=1.0)
    note: str


class CandidateSummary(BaseModel):
    """Top-level summary of a candidate evaluated during resolution."""
    patient_id: str
    hospital_id: str
    name: str
    score: float = Field(..., ge=0.0, le=1.0)


class EvidenceBreakdown(BaseModel):
    """
    Structured evidence produced by the scorer and stored in
    ResolutionDecision.evidence_breakdown as JSON.
    """
    fields: dict[str, FieldEvidence] = Field(
        default_factory=dict,
        description="Per-field similarity scores and notes",
    )
    top_candidates: list[CandidateSummary] = Field(
        default_factory=list,
        description="Ordered list of evaluated candidates (highest score first)",
    )


# ---------------------------------------------------------------------------
# Resolution Decision
# ---------------------------------------------------------------------------

class ResolutionDecisionRead(BaseModel):
    """Full decision record returned by the API (read-only — decisions are immutable)."""
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    lab_result_id: str
    resolved_at: datetime
    outcome: OutcomeEnum
    matched_patient_id: Optional[str]
    top_score: float
    second_score: Optional[float]
    score_margin: Optional[float]
    candidate_count: int
    evidence_breakdown: dict[str, Any]
    decision_reason: str
    triggered_by: TriggeredByEnum


class ResolutionRequest(BaseModel):
    """
    POST body to trigger an identity resolution for a lab result.
    The engine will look up the LabResult by lab_result_id and run matching.
    """
    lab_result_id: str = Field(..., description="ID of the LabResult to resolve")
    triggered_by: TriggeredByEnum = TriggeredByEnum.AUTO
