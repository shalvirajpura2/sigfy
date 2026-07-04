from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanDoc:
    id: str
    filename: str
    title: str
    keywords: tuple[str, ...]


PLAN_DOCS: list[PlanDoc] = [
    PlanDoc("medical_ppo", "MedicalPPOUHC.pdf", "Medical PPO (UHC)",
            ("medical", "deductible", "urgent care", "specialist", "travel", "lodging",
             "transportation", "out-of-network", "coinsurance", "hospital")),
    PlanDoc("dental_ppo", "DentalPPO.pdf", "Dental PPO",
            ("dental", "orthodontic", "orthodontist", "braces", "teeth", "delta dental", "tmj")),
    PlanDoc("vision_basic", "VisionBasic.pdf", "Vision Basic",
            ("vision", "eye", "glasses", "contacts", "lenses", "frames", "exam")),
    PlanDoc("hcsa", "HCSA.pdf", "Health Care Spending Account (Health FSA)",
            ("fsa", "flexible spending", "hcsa", "spending account", "contribution",
             "carryover", "reimbursement")),
    PlanDoc("critical_illness", "CriticalIllness.pdf", "Group Critical Illness Insurance",
            ("critical illness", "aflac", "mercer", "administrator", "lump sum", "diagnosis")),
    PlanDoc("hospital_indemnity", "HospitalIndemnity.pdf", "Group Hospital Indemnity Insurance",
            ("hospital indemnity", "admission", "confinement", "aflac", "administrator")),
    PlanDoc("long_term_care", "LongTermCare.pdf", "Long-Term Care Insurance",
            ("long term care", "long-term care", "ltc", "genworth", "nursing", "enroll",
             "enrollment", "custodial")),
    PlanDoc("wellness", "Wellness.pdf", "Wellness",
            ("wellness", "screening", "biometric", "incentive", "reward", "preventive")),
]

BY_ID = {d.id: d for d in PLAN_DOCS}
BY_FILENAME = {d.filename: d for d in PLAN_DOCS}
