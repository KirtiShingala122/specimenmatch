from typing import Dict, Any, Tuple
from rapidfuzz import fuzz

from backend.models import Patient
from backend.matching import normalizer

# Tunable weights
WEIGHT_DOB = 30.0
WEIGHT_LAST_NAME = 25.0
WEIGHT_FIRST_NAME = 20.0
WEIGHT_PHONE = 15.0
WEIGHT_GENDER = 5.0
WEIGHT_ADDRESS = 5.0


def score_candidate(lab_demographics: Dict[str, Any], candidate: Patient) -> Tuple[float, Dict[str, float], str]:
    """
    Scores a candidate patient against raw lab demographics.
    Returns: (overall_score, field_scores, evidence_reason)
    """
    # 1. Normalize lab demographics
    lab_fname = normalizer.normalize_name(lab_demographics.get("first_name"))
    lab_lname = normalizer.normalize_name(lab_demographics.get("last_name"))
    lab_dob = normalizer.normalize_dob(lab_demographics.get("dob"))
    lab_gender = normalizer.normalize_gender(lab_demographics.get("gender"))
    lab_phone = normalizer.normalize_phone(lab_demographics.get("phone"))
    lab_address = normalizer.normalize_address(lab_demographics.get("address"))

    # 2. Normalize candidate demographics
    cand_fname = normalizer.normalize_name(candidate.first_name)
    cand_lname = normalizer.normalize_name(candidate.last_name)
    
    cand_dob_str = None
    if candidate.date_of_birth:
        cand_dob_str = candidate.date_of_birth.strftime("%Y-%m-%d")
        
    cand_gender = normalizer.normalize_gender(candidate.gender.value if candidate.gender else None)
    cand_phone = normalizer.normalize_phone(candidate.phone)
    cand_address = normalizer.normalize_address(candidate.address_line1)

    # 3. Calculate field-level similarities
    field_scores = {}
    earned_score = 0.0
    possible_score = 0.0

    # First Name
    if lab_fname and cand_fname:
        sim = fuzz.ratio(lab_fname, cand_fname) / 100.0
        field_scores["first_name"] = sim
        earned_score += sim * WEIGHT_FIRST_NAME
        possible_score += WEIGHT_FIRST_NAME

    # Last Name
    if lab_lname and cand_lname:
        sim = fuzz.ratio(lab_lname, cand_lname) / 100.0
        field_scores["last_name"] = sim
        earned_score += sim * WEIGHT_LAST_NAME
        possible_score += WEIGHT_LAST_NAME

    # DOB
    if lab_dob and cand_dob_str:
        sim = 1.0 if lab_dob == cand_dob_str else 0.0
        field_scores["dob"] = sim
        earned_score += sim * WEIGHT_DOB
        possible_score += WEIGHT_DOB

    # Gender
    if lab_gender and cand_gender:
        sim = 1.0 if lab_gender == cand_gender else 0.0
        field_scores["gender"] = sim
        earned_score += sim * WEIGHT_GENDER
        possible_score += WEIGHT_GENDER

    # Phone
    if lab_phone and cand_phone:
        # Check if one is a substring of the other (e.g. missing country code)
        if lab_phone in cand_phone or cand_phone in lab_phone:
            sim = 1.0
        else:
            sim = fuzz.ratio(lab_phone, cand_phone) / 100.0
        field_scores["phone"] = sim
        earned_score += sim * WEIGHT_PHONE
        possible_score += WEIGHT_PHONE

    # Address
    if lab_address and cand_address:
        sim = fuzz.token_set_ratio(lab_address, cand_address) / 100.0
        field_scores["address"] = sim
        earned_score += sim * WEIGHT_ADDRESS
        possible_score += WEIGHT_ADDRESS

    # 4. Calculate overall score normalized by available evidence
    if possible_score == 0:
        return 0.0, field_scores, "No shared demographic fields available to compare."

    overall_score = earned_score / possible_score
    
    # Track missing evidence context
    reason = f"Scored on {len(field_scores)} fields (Max weight available: {possible_score})."

    return overall_score, field_scores, reason
