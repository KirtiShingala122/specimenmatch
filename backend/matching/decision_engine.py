from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.models import OutcomeEnum, Patient
from backend.matching import normalizer
from backend.matching.candidate_gen import generate_candidates
from backend.matching.scorer import score_candidate

# Configurable MVP thresholds (Not Medically Validated)
MATCH_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.50
MARGIN_THRESHOLD = 0.15


def resolve_identity(db_session: Session, raw_demographics: Dict[str, Any]) -> dict:
    """
    Core decision engine for specimen identity resolution.
    Returns a dictionary containing the resolution decision metadata.
    """
    # 1. Extract and normalize signals for blocking
    norm_lname = normalizer.normalize_name(raw_demographics.get("last_name"))
    norm_dob = normalizer.normalize_dob(raw_demographics.get("dob"))
    norm_phone = normalizer.normalize_phone(raw_demographics.get("phone"))

    # 2. Generate candidates
    candidates = generate_candidates(db_session, norm_lname, norm_dob, norm_phone)

    if not candidates:
        return _build_decision(OutcomeEnum.NO_MATCH, None, 0.0, None, 0.0, 0, {}, "No sufficiently similar candidate found")

    # 3. Score all candidates
    scored_candidates = []
    for cand in candidates:
        score, field_scores, evidence_reason = score_candidate(raw_demographics, cand)
        scored_candidates.append({
            "candidate": cand,
            "score": score,
            "field_scores": field_scores,
            "evidence_reason": evidence_reason
        })

    # Sort by score descending
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    best_match = scored_candidates[0]
    best_score = best_match["score"]
    
    second_score = None
    margin = None
    
    if len(scored_candidates) > 1:
        second_score = scored_candidates[1]["score"]
        margin = best_score - second_score

    candidate_count = len(scored_candidates)

    # 4. Evaluate Safety Rules
    # Rule A: Weak / No Evidence
    if best_score < REVIEW_THRESHOLD:
        return _build_decision(
            OutcomeEnum.NO_MATCH, 
            None, 
            best_score, 
            second_score, 
            margin, 
            candidate_count, 
            best_match["field_scores"], 
            "No candidate met the minimum review threshold."
        )

    # Rule B: Ambiguity / Tie / Insufficient Separation
    if margin is not None and margin < MARGIN_THRESHOLD and best_score >= REVIEW_THRESHOLD:
        return _build_decision(
            OutcomeEnum.REVIEW_REQUIRED, 
            None, 
            best_score, 
            second_score, 
            margin, 
            candidate_count, 
            best_match["field_scores"], 
            "Two candidates have similar scores; manual review required."
        )

    # Rule C: Reasonable evidence but not strong enough for auto-match
    if best_score >= REVIEW_THRESHOLD and best_score < MATCH_THRESHOLD:
        return _build_decision(
            OutcomeEnum.REVIEW_REQUIRED, 
            None, 
            best_score, 
            second_score, 
            margin, 
            candidate_count, 
            best_match["field_scores"], 
            "Candidate found but score is below auto-match confidence threshold."
        )

    # Rule D: Strong score + Clear separation
    if best_score >= MATCH_THRESHOLD:
        # Extra safety check: never auto-match if only a single field was available for scoring
        if len(best_match["field_scores"]) < 2:
            return _build_decision(
                OutcomeEnum.REVIEW_REQUIRED, 
                None, 
                best_score, 
                second_score, 
                margin, 
                candidate_count, 
                best_match["field_scores"], 
                "Score is high but based on insufficient data points (only 1 field)."
            )

        return _build_decision(
            OutcomeEnum.MATCH, 
            best_match["candidate"].patient_id, 
            best_score, 
            second_score, 
            margin, 
            candidate_count, 
            best_match["field_scores"], 
            "Strong demographic agreement with clear candidate separation."
        )

    # Fallback safety net
    return _build_decision(
        OutcomeEnum.REVIEW_REQUIRED, 
        None, 
        best_score, 
        second_score, 
        margin, 
        candidate_count, 
        best_match["field_scores"], 
        "Fallback review triggered."
    )


def _build_decision(
    outcome: OutcomeEnum,
    matched_patient_id: Optional[str],
    top_score: float,
    second_score: Optional[float],
    score_margin: Optional[float],
    candidate_count: int,
    evidence_breakdown: Dict[str, float],
    decision_reason: str
) -> dict:
    return {
        "outcome": outcome.value,
        "matched_patient_id": matched_patient_id,
        "top_score": top_score,
        "second_score": second_score,
        "score_margin": score_margin,
        "candidate_count": candidate_count,
        "evidence_breakdown": evidence_breakdown,
        "decision_reason": decision_reason
    }
