from backend.models import Hospital, LabResult, Patient
from backend.seed.seed_data import reset_and_seed_db


def test_seed_script_executes_and_populates_db(db):
    reset_and_seed_db(db)

    # Check minimum record counts
    assert db.query(Hospital).count() == 3
    assert db.query(Patient).count() >= 35
    assert db.query(LabResult).count() >= 10


def test_demo_scenarios_exist(db):
    reset_and_seed_db(db)

    # Scenario 1: MATCH candidate ("Rahul K.")
    lab_sc1 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-1").first()
    assert lab_sc1 is not None
    assert lab_sc1.raw_demographics["first_name"] == "Rahul"
    assert lab_sc1.raw_demographics["last_name"] == "K."

    # Verify matching candidate exists in hospital DB
    rahul_patient = db.query(Patient).filter_by(first_name="Rahul", last_name="Kumar").first()
    assert rahul_patient is not None

    # Scenario 2: REVIEW_REQUIRED candidate (Ambiguous "Priya Sharma")
    lab_sc2 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-2").first()
    assert lab_sc2 is not None
    assert lab_sc2.raw_demographics["first_name"] == "Priya"

    # Verify multiple candidate patients exist with same name + DOB
    priya_patients = db.query(Patient).filter_by(first_name="Priya", last_name="Sharma").all()
    assert len(priya_patients) >= 2

    # Scenario 3: NO_MATCH candidate ("James Fitzgerald")
    lab_sc3 = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-3").first()
    assert lab_sc3 is not None
    assert lab_sc3.raw_demographics["first_name"] == "James"

    # Verify NO matching patient exists in hospital DB
    james = db.query(Patient).filter_by(first_name="James", last_name="Fitzgerald").first()
    assert james is None
