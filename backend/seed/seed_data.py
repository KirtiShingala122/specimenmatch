import random
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db
from backend.models import GenderEnum, Hospital, LabResult, Patient

random.seed(42)

FIRST_NAMES_MALE = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan", "Shaurya", "Atharva", "Rohan", "Kabir", "Aryan"]
FIRST_NAMES_FEMALE = ["Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Chiara", "Riya", "Anushka", "Myra", "Ahana", "Avani", "Isha", "Kavya", "Tanvi", "Neha"]
LAST_NAMES = ["Patel", "Shah", "Mehta", "Joshi", "Verma", "Gupta", "Deshmukh", "Choudhury", "Bose", "Nair", "Iyer", "Rao", "Reddy", "Menon", "Kapoor"]
CITIES_DATA = [
    ("Mumbai", "Maharashtra", "400001", "Park Street"),
    ("Delhi", "Delhi", "110001", "Connaught Place"),
    ("Bengaluru", "Karnataka", "560001", "MG Road"),
    ("Hyderabad", "Telangana", "500001", "Banjara Hills"),
    ("Ahmedabad", "Gujarat", "380001", "SG Highway"),
    ("Chennai", "Tamil Nadu", "600001", "Anna Salai"),
    ("Kolkata", "West Bengal", "700001", "Salt Lake"),
    ("Pune", "Maharashtra", "411001", "FC Road"),
    ("Jaipur", "Rajasthan", "302001", "MI Road"),
    ("Gurgaon", "Haryana", "122001", "Cyber City"),
]


def reset_and_seed_db(session: Session = None):
    bind = session.get_bind() if session is not None else engine
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)

    if session is None:
        db = next(get_db())
    else:
        db = session

    # 1. Create Hospitals
    hospitals = [
        Hospital(hospital_name="Apex Health System"),
        Hospital(hospital_name="Metro City Medical Center"),
        Hospital(hospital_name="St. Jude Regional Hospital"),
    ]
    db.add_all(hospitals)
    db.commit()
    for h in hospitals:
        db.refresh(h)

    apex_hosp, metro_hosp, stjude_hosp = hospitals

    # 2. Scenario Patients (Explicit)
    # Scenario 1 Patient
    rahul = Patient(
        hospital_id=apex_hosp.hospital_id,
        mrn="APEX-PAT-1001",
        first_name="Rahul",
        last_name="Kumar",
        date_of_birth=date(1988, 4, 12),
        gender=GenderEnum.M,
        phone="9876543210",
        address_line1="123 Park Street, Apt 4B",
        city="Mumbai",
        state="Maharashtra",
        zip_code="400001",
    )

    # Scenario 2 Ambiguous Patients (Same Name, Same DOB, Same Gender, Different Hospitals)
    priya1 = Patient(
        hospital_id=apex_hosp.hospital_id,
        mrn="APEX-PAT-2001",
        first_name="Priya",
        last_name="Sharma",
        date_of_birth=date(1992, 8, 25),
        gender=GenderEnum.F,
        phone=None,
        address_line1="Sector 15",
        city="Gurgaon",
        state="Haryana",
        zip_code="122001",
    )

    priya2 = Patient(
        hospital_id=metro_hosp.hospital_id,
        mrn="METRO-PAT-2002",
        first_name="Priya",
        last_name="Sharma",
        date_of_birth=date(1992, 8, 25),
        gender=GenderEnum.F,
        phone=None,
        address_line1="Connaught Place",
        city="New Delhi",
        state="Delhi",
        zip_code="110001",
    )

    db.add_all([rahul, priya1, priya2])

    # 3. Generate ~35 Random Synthetic Patients
    genders = [GenderEnum.M, GenderEnum.F, GenderEnum.OTHER]
    all_hospitals = [apex_hosp, metro_hosp, stjude_hosp]

    for i in range(35):
        h = random.choice(all_hospitals)
        g = random.choice(genders)
        first_name = random.choice(FIRST_NAMES_MALE) if g == GenderEnum.M else random.choice(FIRST_NAMES_FEMALE)
        last_name = random.choice(LAST_NAMES)
        
        # Random DOB between 18 and 75 years ago
        age_days = random.randint(18 * 365, 75 * 365)
        dob = date.today() - timedelta(days=age_days)
        phone = f"98{random.randint(10000000, 99999999)}" if random.random() > 0.15 else None
        
        city_info = random.choice(CITIES_DATA)
        city_name, state_name, zip_str, street_name = city_info
        bldg_no = random.randint(1, 400)

        p = Patient(
            hospital_id=h.hospital_id,
            mrn=f"{h.hospital_name[:4].upper()}-PAT-{1000 + i}",
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=g,
            phone=phone,
            address_line1=f"{bldg_no} {street_name}",
            city=city_name,
            state=state_name,
            zip_code=zip_str,
        )
        db.add(p)

    db.commit()

    # 4. Lab Results (Explicit Demo Scenarios + Random Lab Results)
    # Scenario 1: MATCH candidate (Demographic variation: "Rahul K.", DD/MM/YYYY DOB, formatted phone, full word gender)
    lab_sc1 = LabResult(
        specimen_id="LAB-SCENARIO-1",
        lab_name="Central Reference Lab",
        raw_demographics={
            "first_name": "Rahul",
            "last_name": "K.",
            "middle_name": "Dev",
            "dob": "12/04/1988",
            "gender": "Male",
            "phone": "+91 98765-43210",
            "address": "123 Park St, Apt 4B, Mumbai",
        },
        result_data={"test_name": "Complete Blood Count (CBC)", "status": "Normal"},
    )

    # Scenario 2: REVIEW_REQUIRED candidate (Ambiguous Priya Sharma, missing phone/address in lab result)
    lab_sc2 = LabResult(
        specimen_id="LAB-SCENARIO-2",
        lab_name="Metro Clinical Diagnostics",
        raw_demographics={
            "first_name": "Priya",
            "last_name": "Sharma",
            "dob": "1992-08-25",
            "gender": "F",
            "phone": None,
            "address": None,
        },
        result_data={"test_name": "Comprehensive Metabolic Panel (CMP)", "status": "Pending"},
    )

    # Scenario 3: NO_MATCH candidate (Non-existent patient)
    lab_sc3 = LabResult(
        specimen_id="LAB-SCENARIO-3",
        lab_name="Apex Diagnostic Center",
        raw_demographics={
            "first_name": "James",
            "last_name": "Fitzgerald",
            "dob": "1975-11-03",
            "gender": "M",
            "phone": "555-0199",
            "address": "742 Evergreen Terrace, Springfield",
        },
        result_data={"test_name": "Lipid Panel", "status": "Completed"},
    )

    # Scenario 4: Partial Data Match (Only first name and DOB provided, no last name or phone)
    lab_sc4 = LabResult(
        specimen_id="LAB-SCENARIO-4",
        lab_name="Express Care Clinic",
        raw_demographics={
            "first_name": "Rahul",
            "last_name": None,
            "dob": "1988-04-12",
            "gender": None,
            "phone": None,
            "address": None,
        },
        result_data={"test_name": "Basic Metabolic Panel (BMP)", "status": "Pending"},
    )

    db.add_all([lab_sc1, lab_sc2, lab_sc3, lab_sc4])

    # Add 7 extra lab results with realistic noise
    sample_patients = db.query(Patient).limit(7).all()
    for idx, pat in enumerate(sample_patients):
        # Slightly alter demographic format
        raw_dob = pat.date_of_birth.strftime("%Y/%m/%d") if idx % 2 == 0 else pat.date_of_birth.strftime("%d-%m-%Y")
        db.add(
            LabResult(
                specimen_id=f"LAB-EXTRA-{100 + idx}",
                lab_name="Regional Express Pathology",
                raw_demographics={
                    "first_name": pat.first_name.lower() if idx % 3 == 0 else pat.first_name,
                    "last_name": pat.last_name,
                    "dob": raw_dob,
                    "gender": pat.gender.value,
                    "phone": pat.phone,
                    "address": f"{pat.address_line1}, {pat.city}" if pat.address_line1 else None,
                },
                result_data={"test_name": "Urinalysis", "status": "Completed"},
            )
        )

    db.commit()

    print("Database seeded successfully!")
    print(f"Hospitals: {db.query(Hospital).count()}")
    print(f"Patients: {db.query(Patient).count()}")
    print(f"Lab Results: {db.query(LabResult).count()}")


if __name__ == "__main__":
    reset_and_seed_db()

