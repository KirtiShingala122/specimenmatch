"""
test_models.py — Tests for ORM models and database initialization.

Covers:
  1. DB initialization creates all four tables.
  2. Hospital CRUD.
  3. Patient CRUD (linked to a hospital).
  4. LabResult creation with raw_demographics JSON.
  5. ResolutionDecision creation for all three outcome types.
  6. Relationship traversal (patient → hospital, decision → lab result).
  7. Enum validation for OutcomeEnum and GenderEnum.
  8. Nullable fields behave correctly.
  9. Cascade delete: deleting a hospital deletes its patients.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import inspect, text

from backend.models import (
    GenderEnum,
    Hospital,
    LabResult,
    OutcomeEnum,
    Patient,
    ResolutionDecision,
    TriggeredByEnum,
)


# ---------------------------------------------------------------------------
# 1. Table existence
# ---------------------------------------------------------------------------

def test_all_tables_created(engine):
    """All four tables must exist after init."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "hospitals" in tables, "hospitals table missing"
    assert "patients" in tables, "patients table missing"
    assert "lab_results" in tables, "lab_results table missing"
    assert "resolution_decisions" in tables, "resolution_decisions table missing"


# ---------------------------------------------------------------------------
# 2. Hospital
# ---------------------------------------------------------------------------

def test_create_hospital(db):
    hospital = Hospital(hospital_name="City General Hospital")
    db.add(hospital)
    db.flush()

    fetched = db.query(Hospital).filter_by(hospital_name="City General Hospital").one()
    assert fetched.hospital_id is not None
    assert fetched.hospital_name == "City General Hospital"
    assert fetched.created_at is not None


def test_hospital_name_is_unique(db):
    """Inserting two hospitals with the same name must fail."""
    from sqlalchemy.exc import IntegrityError

    db.add(Hospital(hospital_name="Duplicate Hospital"))
    db.flush()

    with pytest.raises(IntegrityError):
        db.add(Hospital(hospital_name="Duplicate Hospital"))
        db.flush()


# ---------------------------------------------------------------------------
# 3. Patient
# ---------------------------------------------------------------------------

def test_create_patient_linked_to_hospital(db):
    hospital = Hospital(hospital_name="Metro Medical Center")
    db.add(hospital)
    db.flush()

    patient = Patient(
        hospital_id=hospital.hospital_id,
        mrn="MMC-001",
        first_name="Rahul",
        last_name="Kumar",
        date_of_birth=date(1990, 3, 12),
        gender=GenderEnum.M,
        phone="9876543210",
        city="Mumbai",
        state="Maharashtra",
        zip_code="400001",
    )
    db.add(patient)
    db.flush()

    fetched = db.query(Patient).filter_by(mrn="MMC-001").one()
    assert fetched.first_name == "Rahul"
    assert fetched.last_name == "Kumar"
    assert fetched.date_of_birth == date(1990, 3, 12)
    assert fetched.gender == GenderEnum.M
    assert fetched.hospital_id == hospital.hospital_id


def test_patient_optional_fields_nullable(db):
    """A patient can be created with only the mandatory fields."""
    hospital = Hospital(hospital_name="Minimal Fields Hospital")
    db.add(hospital)
    db.flush()

    patient = Patient(
        hospital_id=hospital.hospital_id,
        mrn="MFH-001",
        first_name="Priya",
        last_name="Sharma",
        date_of_birth=date(1985, 7, 15),
        gender=GenderEnum.F,
    )
    db.add(patient)
    db.flush()

    fetched = db.query(Patient).filter_by(mrn="MFH-001").one()
    assert fetched.phone is None
    assert fetched.address_line1 is None
    assert fetched.middle_name is None


def test_patient_relationship_to_hospital(db):
    """Accessing patient.hospital must return the owning Hospital row."""
    hospital = Hospital(hospital_name="Relationship Test Hospital")
    db.add(hospital)
    db.flush()

    patient = Patient(
        hospital_id=hospital.hospital_id,
        mrn="RTH-001",
        first_name="Amir",
        last_name="Khan",
        date_of_birth=date(1975, 11, 1),
        gender=GenderEnum.M,
    )
    db.add(patient)
    db.flush()
    db.refresh(patient)

    assert patient.hospital.hospital_name == "Relationship Test Hospital"


def test_cascade_delete_hospital_removes_patients(db):
    """Deleting a hospital must cascade-delete its patients."""
    hospital = Hospital(hospital_name="Cascade Test Hospital")
    db.add(hospital)
    db.flush()

    for i in range(3):
        db.add(Patient(
            hospital_id=hospital.hospital_id,
            mrn=f"CTH-{i:03d}",
            first_name="Test",
            last_name=f"Patient{i}",
            date_of_birth=date(1990, 1, 1),
            gender=GenderEnum.UNKNOWN,
        ))
    db.flush()

    assert db.query(Patient).filter_by(hospital_id=hospital.hospital_id).count() == 3

    db.delete(hospital)
    db.flush()

    remaining = db.query(Patient).filter_by(hospital_id=hospital.hospital_id).count()
    assert remaining == 0, "Cascade delete did not remove patients"


# ---------------------------------------------------------------------------
# 4. LabResult
# ---------------------------------------------------------------------------

def test_create_lab_result_preserves_raw_demographics(db):
    """raw_demographics must be stored and retrieved exactly as provided."""
    raw = {
        "first_name": "Rahul",
        "last_name": "K.",
        "date_of_birth": "1990-03-12",
        "gender": "M",
        "phone": "(987) 654-3210",
    }
    lab_result = LabResult(
        specimen_id="LAB-SPEC-0001",
        lab_name="Central Diagnostics Lab",
        raw_demographics=raw,
        result_data={"test": "CBC", "result": "Normal"},
    )
    db.add(lab_result)
    db.flush()

    fetched = db.query(LabResult).filter_by(specimen_id="LAB-SPEC-0001").one()
    assert fetched.raw_demographics["last_name"] == "K."
    assert fetched.raw_demographics["phone"] == "(987) 654-3210"
    assert fetched.result_data["test"] == "CBC"


def test_lab_result_specimen_id_unique(db):
    """Two lab results cannot share the same specimen_id."""
    from sqlalchemy.exc import IntegrityError

    db.add(LabResult(
        specimen_id="DUPE-SPEC-001",
        lab_name="Lab A",
        raw_demographics={"first_name": "A"},
    ))
    db.flush()

    with pytest.raises(IntegrityError):
        db.add(LabResult(
            specimen_id="DUPE-SPEC-001",
            lab_name="Lab B",
            raw_demographics={"first_name": "B"},
        ))
        db.flush()


def test_lab_result_result_data_nullable(db):
    """result_data is optional — a lab result can arrive without it."""
    lab_result = LabResult(
        specimen_id="NO-RESULT-001",
        lab_name="Pending Lab",
        raw_demographics={"first_name": "Jane", "last_name": "Doe"},
        result_data=None,
    )
    db.add(lab_result)
    db.flush()

    fetched = db.query(LabResult).filter_by(specimen_id="NO-RESULT-001").one()
    assert fetched.result_data is None


# ---------------------------------------------------------------------------
# 5. ResolutionDecision — all three outcomes
# ---------------------------------------------------------------------------

def _make_hospital_patient_and_lab(db, suffix: str):
    """Helper to create a hospital, patient, and lab result for decision tests."""
    hospital = Hospital(hospital_name=f"Decision Hospital {suffix}")
    db.add(hospital)
    db.flush()

    patient = Patient(
        hospital_id=hospital.hospital_id,
        mrn=f"DH-{suffix}-001",
        first_name="Demo",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender=GenderEnum.M,
    )
    db.add(patient)

    lab_result = LabResult(
        specimen_id=f"SPEC-{suffix}",
        lab_name="Test Lab",
        raw_demographics={"first_name": "Demo", "last_name": "Patient"},
    )
    db.add(lab_result)
    db.flush()

    return hospital, patient, lab_result


def test_resolution_decision_match(db):
    """MATCH decision stores matched_patient_id and a high score."""
    _, patient, lab_result = _make_hospital_patient_and_lab(db, "MATCH")

    evidence = {
        "fields": {
            "last_name": {"score": 1.0, "note": "exact match"},
            "dob": {"score": 1.0, "note": "format difference normalized"},
        },
        "top_candidates": [
            {"patient_id": patient.patient_id, "hospital_id": patient.hospital_id,
             "name": "Demo Patient", "score": 0.97},
        ],
    }

    decision = ResolutionDecision(
        lab_result_id=lab_result.lab_result_id,
        outcome=OutcomeEnum.MATCH,
        matched_patient_id=patient.patient_id,
        top_score=0.97,
        second_score=0.40,
        score_margin=0.57,
        candidate_count=5,
        evidence_breakdown=evidence,
        decision_reason="Strong match on last name, DOB, and phone after normalization.",
        triggered_by=TriggeredByEnum.AUTO,
    )
    db.add(decision)
    db.flush()

    fetched = db.query(ResolutionDecision).filter_by(
        lab_result_id=lab_result.lab_result_id
    ).one()
    assert fetched.outcome == OutcomeEnum.MATCH
    assert fetched.matched_patient_id == patient.patient_id
    assert fetched.top_score == pytest.approx(0.97)
    assert fetched.score_margin == pytest.approx(0.57)
    assert fetched.evidence_breakdown["fields"]["last_name"]["score"] == 1.0


def test_resolution_decision_review_required(db):
    """REVIEW_REQUIRED decision has null matched_patient_id and low margin."""
    _, _, lab_result = _make_hospital_patient_and_lab(db, "REVIEW")

    decision = ResolutionDecision(
        lab_result_id=lab_result.lab_result_id,
        outcome=OutcomeEnum.REVIEW_REQUIRED,
        matched_patient_id=None,  # Cannot safely assign
        top_score=0.88,
        second_score=0.87,
        score_margin=0.01,
        candidate_count=2,
        evidence_breakdown={
            "fields": {"last_name": {"score": 1.0, "note": "exact"}, "dob": {"score": 1.0, "note": "exact"}},
            "top_candidates": [],
        },
        decision_reason="Two candidates score nearly identically (margin=0.01 < threshold 0.15). Human review required.",
        triggered_by=TriggeredByEnum.AUTO,
    )
    db.add(decision)
    db.flush()

    fetched = db.query(ResolutionDecision).filter_by(
        lab_result_id=lab_result.lab_result_id
    ).one()
    assert fetched.outcome == OutcomeEnum.REVIEW_REQUIRED
    assert fetched.matched_patient_id is None
    assert fetched.score_margin == pytest.approx(0.01)


def test_resolution_decision_no_match(db):
    """NO_MATCH decision has null matched_patient_id and very low top_score."""
    _, _, lab_result = _make_hospital_patient_and_lab(db, "NOMATCH")

    decision = ResolutionDecision(
        lab_result_id=lab_result.lab_result_id,
        outcome=OutcomeEnum.NO_MATCH,
        matched_patient_id=None,
        top_score=0.22,
        second_score=None,
        score_margin=None,
        candidate_count=0,
        evidence_breakdown={"fields": {}, "top_candidates": []},
        decision_reason="No candidate exceeded the minimum plausibility threshold of 0.50.",
        triggered_by=TriggeredByEnum.MANUAL,
    )
    db.add(decision)
    db.flush()

    fetched = db.query(ResolutionDecision).filter_by(
        lab_result_id=lab_result.lab_result_id
    ).one()
    assert fetched.outcome == OutcomeEnum.NO_MATCH
    assert fetched.matched_patient_id is None
    assert fetched.second_score is None
    assert fetched.score_margin is None
    assert fetched.triggered_by == TriggeredByEnum.MANUAL


# ---------------------------------------------------------------------------
# 6. Relationship traversal
# ---------------------------------------------------------------------------

def test_lab_result_to_decision_relationship(db):
    """lab_result.resolution_decisions must contain the linked decision."""
    _, _, lab_result = _make_hospital_patient_and_lab(db, "REL")

    decision = ResolutionDecision(
        lab_result_id=lab_result.lab_result_id,
        outcome=OutcomeEnum.NO_MATCH,
        matched_patient_id=None,
        top_score=0.1,
        candidate_count=0,
        evidence_breakdown={},
        decision_reason="No match.",
        triggered_by=TriggeredByEnum.AUTO,
    )
    db.add(decision)
    db.flush()
    db.refresh(lab_result)

    assert len(lab_result.resolution_decisions) == 1
    assert lab_result.resolution_decisions[0].outcome == OutcomeEnum.NO_MATCH
