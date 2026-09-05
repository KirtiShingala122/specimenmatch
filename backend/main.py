from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from backend.database import engine, get_db, Base
from backend.models import Patient, LabResult, ResolutionDecision, OutcomeEnum, TriggeredByEnum
from backend.schemas import PatientRead, LabResultRead, LabResultCreate, ResolutionDecisionRead, ResolutionRequest
from backend.matching.decision_engine import resolve_identity
import datetime

# Ensure tables are created (just in case)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SpecimenMatch API", description="Core safety-first specimen identity resolution engine.")

# Add CORS for React frontend (Phase 5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/patients", response_model=List[PatientRead])
def get_patients(db: Session = Depends(get_db)):
    """Return all synthetic patient records."""
    return db.query(Patient).all()


@app.get("/lab-results", response_model=List[LabResultRead])
def get_lab_results(db: Session = Depends(get_db)):
    """Return seeded synthetic lab results."""
    return db.query(LabResult).order_by(LabResult.submitted_at.desc()).all()


@app.post("/lab-results", response_model=LabResultRead)
def create_lab_result(request: LabResultCreate, db: Session = Depends(get_db)):
    """Add a dynamic custom lab result to test the matching engine."""
    import uuid
    new_result = LabResult(
        lab_result_id=str(uuid.uuid4()),
        specimen_id=request.specimen_id,
        lab_name=request.lab_name,
        submitted_at=datetime.datetime.utcnow(),
        raw_demographics=request.raw_demographics.dict(exclude_none=True),
        result_data=request.result_data or {}
    )
    db.add(new_result)
    db.commit()
    db.refresh(new_result)
    return new_result


@app.get("/decisions", response_model=List[ResolutionDecisionRead])
def get_decisions(db: Session = Depends(get_db)):
    """Return resolution decisions/audit log."""
    return db.query(ResolutionDecision).order_by(ResolutionDecision.resolved_at.desc()).all()


@app.post("/resolve", response_model=ResolutionDecisionRead)
def resolve_specimen(request: ResolutionRequest, db: Session = Depends(get_db)):
    """
    Run the core matching engine on a specific lab result.
    Persists the decision to the audit log.
    """
    lab_result = db.query(LabResult).filter(LabResult.lab_result_id == request.lab_result_id).first()
    if not lab_result:
        raise HTTPException(status_code=404, detail="Lab result not found")

    # Run the deterministic matching engine
    decision_metadata = resolve_identity(db, lab_result.raw_demographics)

    # Persist the decision
    decision = ResolutionDecision(
        lab_result_id=lab_result.lab_result_id,
        outcome=OutcomeEnum(decision_metadata["outcome"]),
        matched_patient_id=decision_metadata["matched_patient_id"],
        top_score=decision_metadata["top_score"],
        second_score=decision_metadata["second_score"],
        score_margin=decision_metadata["score_margin"],
        candidate_count=decision_metadata["candidate_count"],
        evidence_breakdown=decision_metadata["evidence_breakdown"],
        decision_reason=decision_metadata["decision_reason"],
        triggered_by=request.triggered_by
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    return decision
