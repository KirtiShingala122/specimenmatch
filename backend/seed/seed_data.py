import random
from datetime import date, datetime
from faker import Faker
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db
from backend.models import GenderEnum, Hospital, LabResult, Patient

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)


def reset_and_seed_db(session: Session = None):
    if session is None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
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
<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
    db.add_all([rahul, priya1, priya2])

    # 3. Generate ~35 Random Synthetic Patients
    genders = [GenderEnum.M, GenderEnum.F, GenderEnum.OTHER]
    all_hospitals = [apex_hosp, metro_hosp, stjude_hosp]

    for i in range(35):
        h = random.choice(all_hospitals)
        g = random.choice(genders)
        first_name = fake.first_name_male() if g == GenderEnum.M else fake.first_name_female()
        last_name = fake.last_name()
        dob = fake.date_of_birth(minimum_age=18, maximum_age=80)
        phone = fake.phone_number() if random.random() > 0.15 else None

        p = Patient(
            hospital_id=h.hospital_id,
            mrn=f"{h.hospital_name[:4].upper()}-PAT-{1000 + i}",
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=g,
            phone=phone,
            address_line1=fake.street_address(),
            city=fake.city(),
            state=fake.state(),
            zip_code=fake.postcode(),
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

    db.add_all([lab_sc1, lab_sc2, lab_sc3])

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

