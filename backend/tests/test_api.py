from fastapi.testclient import TestClient
from backend.main import app, get_db
from backend.models import LabResult, ResolutionDecision, OutcomeEnum
from backend.seed.seed_data import reset_and_seed_db

client = TestClient(app)

import pytest

def override_get_db(db_session):
    def _override():
        yield db_session
    return _override

@pytest.fixture(autouse=True)
def override_dependency(db):
    app.dependency_overrides[get_db] = override_get_db(db)
    yield
    app.dependency_overrides.clear()

def test_get_patients(db):
    reset_and_seed_db(db)
    response = client.get("/patients")
    assert response.status_code == 200
    assert len(response.json()) >= 35


def test_get_lab_results(db):
    reset_and_seed_db(db)
    response = client.get("/lab-results")
    assert response.status_code == 200
    assert len(response.json()) >= 10


def test_resolve_scenario_1_match(db):
    reset_and_seed_db(db)
    # Get the lab result ID for scenario 1
    lab = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-1").first()
    
    response = client.post("/resolve", json={"lab_result_id": lab.lab_result_id})
    assert response.status_code == 200
    
    data = response.json()
    assert data["outcome"] == OutcomeEnum.MATCH.value
    assert data["matched_patient_id"] is not None
    assert data["top_score"] >= 0.80
    
    # Verify persistence
    decision = db.query(ResolutionDecision).filter_by(lab_result_id=lab.lab_result_id).first()
    assert decision is not None
    assert decision.outcome == OutcomeEnum.MATCH


def test_resolve_scenario_2_review_required(db):
    reset_and_seed_db(db)
    lab = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-2").first()
    
    response = client.post("/resolve", json={"lab_result_id": lab.lab_result_id})
    assert response.status_code == 200
    
    data = response.json()
    assert data["outcome"] == OutcomeEnum.REVIEW_REQUIRED.value
    assert data["matched_patient_id"] is None
    
    # Verify persistence
    decision = db.query(ResolutionDecision).filter_by(lab_result_id=lab.lab_result_id).first()
    assert decision is not None
    assert decision.outcome == OutcomeEnum.REVIEW_REQUIRED


def test_resolve_scenario_3_no_match(db):
    reset_and_seed_db(db)
    lab = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-3").first()
    
    response = client.post("/resolve", json={"lab_result_id": lab.lab_result_id})
    assert response.status_code == 200
    
    data = response.json()
    assert data["outcome"] == OutcomeEnum.NO_MATCH.value
    
    # Verify persistence
    decision = db.query(ResolutionDecision).filter_by(lab_result_id=lab.lab_result_id).first()
    assert decision is not None
    assert decision.outcome == OutcomeEnum.NO_MATCH


def test_get_decisions(db):
    reset_and_seed_db(db)
    
    # Seed a decision by calling the API once
    lab = db.query(LabResult).filter_by(specimen_id="LAB-SCENARIO-1").first()
    client.post("/resolve", json={"lab_result_id": lab.lab_result_id})
    
    response = client.get("/decisions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["outcome"] == OutcomeEnum.MATCH.value
