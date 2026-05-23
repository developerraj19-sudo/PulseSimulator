// ============================================================================
// PulseSim: Neo4j Cypher Schema & Data Seeding
// Phase 1: Database Initialization
// ============================================================================

// 1. Database Constraints & Indexes
CREATE CONSTRAINT unique_case_id IF NOT EXISTS 
FOR (c:ClinicalCase) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT unique_disease_name IF NOT EXISTS 
FOR (d:Disease) REQUIRE d.name IS UNIQUE;

// 2. CASE 1: Acute Appendicitis (Intermediate)
MERGE (c1:ClinicalCase {id: "case_appendicitis_001"})
SET c1.title = "Acute Right Lower Quadrant Pain",
    c1.difficulty = "Intermediate",
    c1.patient_age = 24,
    c1.patient_gender = "Male",
    c1.patient_personality = "Anxious and protective of his abdomen. Reluctant to move. Speaks politely but is clearly in pain.",
    c1.baseline_hr = 92.0,
    c1.baseline_bps = 122.0,
    c1.baseline_bpd = 78.0,
    c1.baseline_spo2 = 98.0,
    c1.baseline_temp = 38.2,
    c1.anxiety = 50.0;

MERGE (d1:Disease {name: "Acute Appendicitis"})
SET d1.icd10_code = "K35.80",
    d1.description = "Acute appendicitis without localized peritonitis. Requires surgical evaluation.";

MERGE (c1)-[:PRESENTING_WITH]->(d1);

// Symptoms for Appendicitis
MERGE (s1_1:Symptom {name: "Right lower quadrant pain"})
SET s1_1.baseline_severity = 7.0, s1_1.body_part = "Abdomen";

MERGE (s1_2:Symptom {name: "Nausea and vomiting"})
SET s1_2.baseline_severity = 4.0, s1_2.body_part = "Gastrointestinal";

MERGE (s1_3:Symptom {name: "Low grade fever"})
SET s1_3.baseline_severity = 3.0, s1_3.body_part = "Systemic";

MERGE (s1_4:Symptom {name: "Loss of appetite"})
SET s1_4.baseline_severity = 6.0, s1_4.body_part = "Systemic";

MERGE (d1)-[:EXHIBITS {probability: 0.95}]->(s1_1);
MERGE (d1)-[:EXHIBITS {probability: 0.80}]->(s1_2);
MERGE (d1)-[:EXHIBITS {probability: 0.70}]->(s1_3);
MERGE (d1)-[:EXHIBITS {probability: 0.90}]->(s1_4);

// Lab Results for Appendicitis
MERGE (l1_1:LabResult {test_name: "Complete Blood Count", parameter: "White Blood Cell Count", value: "14.5", unit: "10^9/L"})
MERGE (l1_2:LabResult {test_name: "Complete Blood Count", parameter: "Neutrophils", value: "82.0", unit: "%"})
MERGE (l1_3:LabResult {test_name: "Comprehensive Metabolic Panel", parameter: "Sodium", value: "139.0", unit: "mEq/L"})
MERGE (l1_4:LabResult {test_name: "Comprehensive Metabolic Panel", parameter: "Potassium", value: "4.1", unit: "mEq/L"})

MERGE (d1)-[:HAS_LAB_PROFILE]->(l1_1);
MERGE (d1)-[:HAS_LAB_PROFILE]->(l1_2);
MERGE (d1)-[:HAS_LAB_PROFILE]->(l1_3);
MERGE (d1)-[:HAS_LAB_PROFILE]->(l1_4);


// 3. CASE 2: Acute Anaphylaxis (Hard - Rapidly Deteriorating)
MERGE (c2:ClinicalCase {id: "case_anaphylaxis_001"})
SET c2.title = "Acute Respiratory Distress and Hypotension",
    c2.difficulty = "Hard",
    c2.patient_age = 35,
    c2.patient_gender = "Female",
    c2.patient_personality = "Extremely terrified, gasping for air. Speaks in one-word answers, sounds panicked and confused.",
    c2.baseline_hr = 115.0,
    c2.baseline_bps = 88.0,
    c2.baseline_bpd = 52.0,
    c2.baseline_spo2 = 90.0,
    c2.baseline_temp = 36.8,
    c2.anxiety = 95.0;

MERGE (d2:Disease {name: "Anaphylaxis"})
SET d2.icd10_code = "T88.6XXA",
    d2.description = "Severe, life-threatening systemic hypersensitivity reaction characterized by rapid onset of airway, breathing, or circulatory problems.";

MERGE (c2)-[:PRESENTING_WITH]->(d2);

// Symptoms for Anaphylaxis
MERGE (s2_1:Symptom {name: "Dyspnea"})
SET s2_1.baseline_severity = 9.0, s2_1.body_part = "Respiratory";

MERGE (s2_2:Symptom {name: "Diffuse hives and itching"})
SET s2_2.baseline_severity = 7.0, s2_2.body_part = "Skin";

MERGE (s2_3:Symptom {name: "Stridor and wheezing"})
SET s2_3.baseline_severity = 8.0, s2_3.body_part = "Respiratory";

MERGE (s2_4:Symptom {name: "Lightheadedness"})
SET s2_4.baseline_severity = 6.0, s2_4.body_part = "Systemic";

MERGE (d2)-[:EXHIBITS {probability: 0.99}]->(s2_1);
MERGE (d2)-[:EXHIBITS {probability: 0.90}]->(s2_2);
MERGE (d2)-[:EXHIBITS {probability: 0.85}]->(s2_3);
MERGE (d2)-[:EXHIBITS {probability: 0.75}]->(s2_4);

// Lab Results for Anaphylaxis
MERGE (l2_1:LabResult {test_name: "Arterial Blood Gas", parameter: "pH", value: "7.31", unit: ""})
MERGE (l2_2:LabResult {test_name: "Arterial Blood Gas", parameter: "pCO2", value: "49.0", unit: "mmHg"})
MERGE (l2_3:LabResult {test_name: "Arterial Blood Gas", parameter: "pO2", value: "60.0", unit: "mmHg"})
MERGE (l2_4:LabResult {test_name: "Serum Tryptase", parameter: "Total Tryptase", value: "45.0", unit: "mcg/L"})

MERGE (d2)-[:HAS_LAB_PROFILE]->(l2_1);
MERGE (d2)-[:HAS_LAB_PROFILE]->(l2_2);
MERGE (d2)-[:HAS_LAB_PROFILE]->(l2_3);
MERGE (d2)-[:HAS_LAB_PROFILE]->(l2_4);
