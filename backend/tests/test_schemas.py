"""
test_schemas.py — Tests for Pydantic v2 schemas.

Covers:
  1. Valid HospitalCreate / HospitalRead round-trips.
  2. Valid PatientCreate / PatientRead round-trips.
  3. LabResultDemographics accepts free-form DOB strings.
  4. EvidenceBreakdown serializes correctly.
  5. ResolutionRequest defaults.
  6. Invalid inputs are rejected by Pydantic validators.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from backend.models import GenderEnum, OutcomeEnum, TriggeredByEnum
from backend.schemas import (
    CandidateSummary,
    EvidenceBreakdown,
    FieldEvidence,
    HospitalCreate,
    HospitalRead,
    LabResultCreate,
    LabResultDemographics,
    PatientCreate,
    PatientRead,
    ResolutionDecisionRead,
    ResolutionRequest,
)


# ---------------------------------------------------------------------------
# Hospital schemas
# ---------------------------------------------------------------------------

def test_hospital_create_valid():
    h = HospitalCreate(hospital_name="City General Hospital")
    assert h.hospital_name == "City General Hospital"


def test_hospital_create_empty_name_rejected():
    with pytest.raises(ValidationError):
        HospitalCreate(hospital_name="")


def test_hospital_read_from_orm_dict():
    data = {
        "hospital_id": "abc-123",
        "hospital_name": "Metro Medical",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    h = HospitalRead(**data)
    assert h.hospital_id == "abc-123"
    assert h.hospital_name == "Metro Medical"


# ---------------------------------------------------------------------------
# Patient schemas
# ---------------------------------------------------------------------------

def test_patient_create_minimal():
    """Only mandatory fields — all optional fields should default to None."""
    p = PatientCreate(
        hospital_id="hosp-001",
        mrn="MRN-001",
        first_name="Priya",
        last_name="Sharma",
        date_of_birth=date(1985, 7, 15),
        gender=GenderEnum.F,
    )
    assert p.middle_name is None
    assert p.phone is None
    assert p.city is None


def test_patient_create_full():
    p = PatientCreate(
        hospital_id="hosp-001",
        mrn="MRN-002",
        first_name="Rahul",
        last_name="Kumar",
        middle_name="V.",
        date_of_birth=date(1990, 3, 12),
        gender=GenderEnum.M,
        phone="9876543210",
        address_line1="12 Main St",
        city="Mumbai",
        state="Maharashtra",
        zip_code="400001",
    )
    assert p.first_name == "Rahul"
    assert p.middle_name == "V."
    assert p.gender == GenderEnum.M


def test_patient_create_missing_mandatory_field_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(
            hospital_id="hosp-001",
            # mrn missing
            first_name="Jane",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender=GenderEnum.F,
        )


def test_patient_gender_default_unknown():
    p = PatientCreate(
        hospital_id="hosp-001",
        mrn="MRN-003",
        first_name="Test",
        last_name="Patient",
        date_of_birth=date(2000, 6, 1),
    )
    assert p.gender == GenderEnum.UNKNOWN


# ---------------------------------------------------------------------------
# LabResult schemas
# ---------------------------------------------------------------------------

def test_lab_result_demographics_accepts_any_dob_format():
    """DOB is stored as a raw string — any format must be accepted."""
    d1 = LabResultDemographics(date_of_birth="12-03-1990")
    d2 = LabResultDemographics(date_of_birth="1990-03-12")
    d3 = LabResultDemographics(date_of_birth="03/12/1990")

    assert d1.date_of_birth == "12-03-1990"
    assert d2.date_of_birth == "1990-03-12"
    assert d3.date_of_birth == "03/12/1990"


def test_lab_result_demographics_all_optional():
    """An empty demographics object is valid (lab may omit all fields)."""
    d = LabResultDemographics()
    assert d.first_name is None
    assert d.last_name is None
    assert d.date_of_birth is None


def test_lab_result_create_valid():
    lr = LabResultCreate(
        specimen_id="LAB-SPEC-9999",
        lab_name="Central Diagnostics",
        raw_demographics=LabResultDemographics(
            first_name="Rahul",
            last_name="K.",
            date_of_birth="1990-03-12",
            phone="(987) 654-3210",
        ),
        result_data={"test": "CBC", "result": "Normal"},
    )
    assert lr.specimen_id == "LAB-SPEC-9999"
    assert lr.raw_demographics.last_name == "K."


def test_lab_result_create_result_data_optional():
    lr = LabResultCreate(
        specimen_id="LAB-SPEC-NO-RESULT",
        lab_name="Pending Lab",
        raw_demographics=LabResultDemographics(first_name="Jane"),
    )
    assert lr.result_data is None


# ---------------------------------------------------------------------------
# Evidence breakdown schema
# ---------------------------------------------------------------------------

def test_evidence_breakdown_structure():
    eb = EvidenceBreakdown(
        fields={
            "last_name": FieldEvidence(score=1.0, note="exact match"),
            "dob": FieldEvidence(score=1.0, note="format difference normalized"),
            "phone": FieldEvidence(score=1.0, note="match after stripping formatting"),
        },
        top_candidates=[
            CandidateSummary(
                patient_id="p-001",
                hospital_id="h-001",
                name="Rahul Kumar",
                score=0.97,
            )
        ],
    )
    assert eb.fields["last_name"].score == 1.0
    assert eb.top_candidates[0].name == "Rahul Kumar"


def test_field_evidence_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        FieldEvidence(score=1.5, note="invalid")


# ---------------------------------------------------------------------------
# ResolutionRequest schema
# ---------------------------------------------------------------------------

def test_resolution_request_default_triggered_by():
    req = ResolutionRequest(lab_result_id="lr-001")
    assert req.triggered_by == TriggeredByEnum.AUTO


def test_resolution_request_manual():
    req = ResolutionRequest(lab_result_id="lr-002", triggered_by=TriggeredByEnum.MANUAL)
    assert req.triggered_by == TriggeredByEnum.MANUAL


# ---------------------------------------------------------------------------
# ResolutionDecisionRead schema
# ---------------------------------------------------------------------------

def test_resolution_decision_read_match():
    data = {
        "decision_id": "d-001",
        "lab_result_id": "lr-001",
        "resolved_at": datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        "outcome": OutcomeEnum.MATCH,
        "matched_patient_id": "p-001",
        "top_score": 0.97,
        "second_score": 0.40,
        "score_margin": 0.57,
        "candidate_count": 5,
        "evidence_breakdown": {"fields": {}, "top_candidates": []},
        "decision_reason": "Strong match.",
        "triggered_by": TriggeredByEnum.AUTO,
    }
    d = ResolutionDecisionRead(**data)
    assert d.outcome == OutcomeEnum.MATCH
    assert d.matched_patient_id == "p-001"
    assert d.score_margin == pytest.approx(0.57)


def test_resolution_decision_read_no_match_nullables():
    data = {
        "decision_id": "d-002",
        "lab_result_id": "lr-002",
        "resolved_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "outcome": OutcomeEnum.NO_MATCH,
        "matched_patient_id": None,
        "top_score": 0.22,
        "second_score": None,
        "score_margin": None,
        "candidate_count": 0,
        "evidence_breakdown": {},
        "decision_reason": "No match found.",
        "triggered_by": TriggeredByEnum.AUTO,
    }
    d = ResolutionDecisionRead(**data)
    assert d.outcome == OutcomeEnum.NO_MATCH
    assert d.matched_patient_id is None
    assert d.second_score is None
