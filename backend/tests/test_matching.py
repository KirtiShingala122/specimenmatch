from backend.matching import normalizer
from backend.matching.scorer import score_candidate
from backend.matching.decision_engine import resolve_identity, MATCH_THRESHOLD, REVIEW_THRESHOLD
from backend.models import Patient, GenderEnum, LabResult, OutcomeEnum
from backend.seed.seed_data import reset_and_seed_db

def test_normalization():
    # Names
    assert normalizer.normalize_name("  John  Doe. ") == "john doe"
    assert normalizer.normalize_name(None) is None
    
    # Phone
    assert normalizer.normalize_phone("+91-98765-43210") == "919876543210"
    assert normalizer.normalize_phone(None) is None

    # DOB
    assert normalizer.normalize_dob("1990-12-31") == "1990-12-31"
    assert normalizer.normalize_dob("31/12/1990") == "1990-12-31"
    assert normalizer.normalize_dob("12-31-1990") == "1990-12-31"
    assert normalizer.normalize_dob(None) is None
    assert normalizer.normalize_dob("invalid-date") == "invalid-date"

    # Gender
    assert normalizer.normalize_gender("Male ") == "M"
    assert normalizer.normalize_gender("F") == "F"
    assert normalizer.normalize_gender(None) is None


def test_scoring_logic():
    # Mock candidate
    import datetime
    cand = Patient(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=datetime.date(1990, 1, 1),
        gender=GenderEnum.F,
        phone="5551234",
        address_line1="123 Main St"
    )

    # Strong match
    strong_lab = {
        "first_name": "Jane",
        "last_name": "Doe",
        "dob": "1990-01-01",
        "gender": "Female",
        "phone": "(555) 1234",
        "address": "123 Main St."
    }
    score, fields, reason = score_candidate(strong_lab, cand)
    assert score > 0.95
    assert fields["dob"] == 1.0

    # Missing fields (missing phone and address in lab)
    partial_lab = {
        "first_name": "Jane",
        "last_name": "Doe",
        "dob": "1990-01-01",
        "gender": "F"
    }
    score2, fields2, reason2 = score_candidate(partial_lab, cand)
    assert score2 == 1.0 # 100% on the available evidence
    assert "phone" not in fields2
    assert "address" not in fields2


def test_decision_engine_demo_scenarios(db):
    # Seed the DB so we have the demo scenarios ready
    reset_and_seed_db(db)

    # Scenario 1: MATCH (Rahul)
    lab1 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-1").first()
    res1 = resolve_identity(db, lab1.raw_demographics)
    assert res1["outcome"] == OutcomeEnum.MATCH.value
    assert res1["top_score"] >= MATCH_THRESHOLD
    assert res1["matched_patient_id"] is not None

    # Scenario 2: REVIEW_REQUIRED (Priya ambiguity)
    lab2 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-2").first()
    res2 = resolve_identity(db, lab2.raw_demographics)
    assert res2["outcome"] == OutcomeEnum.REVIEW_REQUIRED.value
    assert res2["candidate_count"] >= 2
    assert res2["score_margin"] < 0.15 # Tied or very close
    assert res2["matched_patient_id"] is None

    # Scenario 3: NO_MATCH (James)
    lab3 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-3").first()
    res3 = resolve_identity(db, lab3.raw_demographics)
    assert res3["outcome"] == OutcomeEnum.NO_MATCH.value
    assert res3["top_score"] < REVIEW_THRESHOLD
    assert res3["matched_patient_id"] is None
