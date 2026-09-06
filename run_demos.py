from backend.database import SessionLocal
from backend.models import LabResult
from backend.matching.decision_engine import resolve_identity
import json

db = SessionLocal()
results = db.query(LabResult).filter(LabResult.specimen_id.in_(['LAB-SCENARIO-1', 'LAB-SCENARIO-2', 'LAB-SCENARIO-3'])).order_by(LabResult.specimen_id).all()

for r in results:
    decision = resolve_identity(db, r.raw_demographics)
    print(f'=== {r.specimen_id} ===')
    print(f'Outcome: {decision["outcome"]}')
    print(f'Top Score: {decision["top_score"]:.2f}')
    print(f'Margin: {decision["score_margin"]:.2f}' if decision["score_margin"] is not None else 'Margin: None')
    print(f'Reason: {decision["decision_reason"]}')
    print('')
db.close()
