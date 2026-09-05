from datetime import date

import pytest

from backend.models import GenderEnum, Hospital, LabResult, OutcomeEnum, Patient, ResolutionDecision, TriggeredByEnum
from backend.schemas import CandidateSummary, EvidenceBreakdown, FieldEvidence, LabResultDemographics


def _hospital(db, name="Test Hospital"):
    h = Hospital(hospital_name=name)
    db.add(h)
    db.flush()
    return h


def _patient(db, hospital_id, mrn="MRN-001"):
    p = Patient(
        hospital_id=hospital_id, mrn=mrn,
        first_name="Rahul", last_name="Kumar",
        date_of_birth=date(1990, 3, 12), gender=GenderEnum.M,
    )
    db.add(p)
    db.flush()
    return p


def _lab_result(db, specimen_id="SPEC-001", demographics=None):
    lr = LabResult(
        specimen_id=specimen_id, lab_name="Central Diagnostics",
        raw_demographics=demographics or {"first_name": "Rahul", "last_name": "K."},
    )
    db.add(lr)
    db.flush()
    return lr


def test_all_tables_created(engine):
    from sqlalchemy import inspect
    tables = inspect(engine).get_table_names()
    assert {"hospitals", "patients", "lab_results", "resolution_decisions"}.issubset(set(tables))


def test_raw_demographics_preserved_exactly(db):
    """Raw lab data must survive the DB round-trip unchanged — engine normalizes, not the DB."""
    raw = {"last_name": "K.", "date_of_birth": "12-03-1990", "phone": "(987) 654-3210"}
    _lab_result(db, "SPEC-PRESERVE", raw)
    assert db.query(LabResult).filter_by(specimen_id="SPEC-PRESERVE").one().raw_demographics == raw


def test_decision_match_outcome(db):
    h = _hospital(db, "H-MATCH")
    p = _patient(db, h.hospital_id)
    lr = _lab_result(db, "SPEC-MATCH")
    db.add(ResolutionDecision(
        lab_result_id=lr.lab_result_id, outcome=OutcomeEnum.MATCH,
        matched_patient_id=p.patient_id, top_score=0.97, second_score=0.40,
        score_margin=0.57, candidate_count=5,
        evidence_breakdown={"fields": {}, "top_candidates": []},
        decision_reason="Strong match after normalization.", triggered_by=TriggeredByEnum.AUTO,
    ))
    db.flush()
    d = db.query(ResolutionDecision).filter_by(lab_result_id=lr.lab_result_id).one()
    assert d.outcome == OutcomeEnum.MATCH
    assert d.matched_patient_id == p.patient_id
    assert d.score_margin == pytest.approx(0.57)


def test_decision_review_required_outcome(db):
    """Collapsed margin must produce REVIEW_REQUIRED with no patient assigned."""
    lr = _lab_result(db, "SPEC-REVIEW")
    db.add(ResolutionDecision(
        lab_result_id=lr.lab_result_id, outcome=OutcomeEnum.REVIEW_REQUIRED,
        matched_patient_id=None, top_score=0.88, second_score=0.87,
        score_margin=0.01, candidate_count=2,
        evidence_breakdown={"fields": {}, "top_candidates": []},
        decision_reason="Margin 0.01 < 0.15 threshold. Human review required.",
        triggered_by=TriggeredByEnum.AUTO,
    ))
    db.flush()
    d = db.query(ResolutionDecision).filter_by(lab_result_id=lr.lab_result_id).one()
    assert d.outcome == OutcomeEnum.REVIEW_REQUIRED
    assert d.matched_patient_id is None


def test_decision_no_match_outcome(db):
    lr = _lab_result(db, "SPEC-NOMATCH")
    db.add(ResolutionDecision(
        lab_result_id=lr.lab_result_id, outcome=OutcomeEnum.NO_MATCH,
        matched_patient_id=None, top_score=0.22, second_score=None,
        score_margin=None, candidate_count=0,
        evidence_breakdown={"fields": {}, "top_candidates": []},
        decision_reason="No candidate exceeded threshold 0.50.",
        triggered_by=TriggeredByEnum.AUTO,
    ))
    db.flush()
    d = db.query(ResolutionDecision).filter_by(lab_result_id=lr.lab_result_id).one()
    assert d.outcome == OutcomeEnum.NO_MATCH
    assert d.matched_patient_id is None
    assert d.second_score is None


def test_dob_accepted_in_any_format():
    """DOB must not be parsed — stored raw for the matching engine to handle."""
    assert LabResultDemographics(date_of_birth="12-03-1990").date_of_birth == "12-03-1990"
    assert LabResultDemographics(date_of_birth="1990-03-12").date_of_birth == "1990-03-12"


def test_evidence_breakdown_contract():
    """evidence_breakdown shape is a UI contract — fields + ranked candidates."""
    eb = EvidenceBreakdown(
        fields={"dob": FieldEvidence(score=1.0, note="format normalized")},
        top_candidates=[
            CandidateSummary(patient_id="p-1", hospital_id="h-1", name="Rahul Kumar", score=0.97),
            CandidateSummary(patient_id="p-2", hospital_id="h-2", name="Rahul Kumar", score=0.40),
        ],
    )
    assert eb.top_candidates[0].score > eb.top_candidates[1].score
