from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from backend.models import Patient


def generate_candidates(
    db_session: Session,
    norm_last_name: Optional[str],
    norm_dob: Optional[str],
    norm_phone: Optional[str] = None
) -> List[Patient]:
    """
    Generates a small candidate set using deterministic blocking.
    A patient becomes a candidate if they match ANY available strong signal.
    Missing fields do not eliminate valid candidates.
    """
    conditions = []

    if norm_last_name:
        # SQLite-friendly: lower() function
        conditions.append(func.lower(Patient.last_name) == norm_last_name)

    if norm_dob:
        try:
            # norm_dob is expected to be YYYY-MM-DD from normalizer
            dob_date = datetime.strptime(norm_dob, "%Y-%m-%d").date()
            conditions.append(Patient.date_of_birth == dob_date)
        except ValueError:
            pass

    if norm_phone:
        # We can do a basic check on phone if it exactly matches, 
        # though DB might have formatted phones. For simple blocking, this is a best-effort OR condition.
        # It's an OR, so if it fails, DOB/Name might still catch them.
        conditions.append(Patient.phone.like(f"%{norm_phone[-4:]}%")) # very loose block on last 4 digits if phone provided

    if not conditions:
        # If no blocking signals exist, we can't safely block.
        # In a real system, we might fallback to other combinations.
        return []

    # Use OR to ensure missing/incorrect fields don't eliminate candidates
    candidates = db_session.query(Patient).filter(or_(*conditions)).all()
    return candidates
