from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models import GenderEnum, OutcomeEnum, TriggeredByEnum


class HospitalCreate(BaseModel):
    hospital_name: str = Field(..., min_length=1, max_length=255)


class HospitalRead(HospitalCreate):
    model_config = ConfigDict(from_attributes=True)
    hospital_id: str
    created_at: datetime


class PatientCreate(BaseModel):
    hospital_id: str
    mrn: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: date
    gender: GenderEnum = GenderEnum.UNKNOWN
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class PatientRead(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    patient_id: str
    created_at: datetime


class LabResultDemographics(BaseModel):
    """All fields optional — DOB stored as raw string, never parsed here."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    dob: Optional[str] = None  # any format: DD-MM-YYYY, YYYY-MM-DD, etc.
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class LabResultCreate(BaseModel):
    specimen_id: str
    lab_name: str
    raw_demographics: LabResultDemographics
    result_data: Optional[dict[str, Any]] = None


class LabResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lab_result_id: str
    specimen_id: str
    lab_name: str
    submitted_at: datetime
    raw_demographics: dict[str, Any]
    result_data: Optional[dict[str, Any]]


class FieldEvidence(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    note: str


class CandidateSummary(BaseModel):
    patient_id: str
    hospital_id: str
    name: str
    score: float = Field(..., ge=0.0, le=1.0)


class EvidenceBreakdown(BaseModel):
    fields: dict[str, FieldEvidence] = Field(default_factory=dict)
    top_candidates: list[CandidateSummary] = Field(default_factory=list)


class ResolutionDecisionRead(BaseModel):
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
    lab_result_id: str
    triggered_by: TriggeredByEnum = TriggeredByEnum.AUTO
