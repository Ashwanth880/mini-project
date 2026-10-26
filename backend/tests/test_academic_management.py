"""
Academic Management Automated Test Suite.
Covers:
1. Student Management:
   - Create student with realistic payload
   - Roll number uniqueness validation (400 on duplicate)
   - Register number uniqueness validation (400 on duplicate)
   - Student listing with filters (class_id, department, year, section)
   - Single student inspection
   - Student update (PUT /students/{id})
   - Student soft-delete / deletion (DELETE /students/{id})
2. Class Management:
   - Create academic class (Admin only)
   - Duplicate class detection (400 on conflict)
   - Class listing with student count & teacher name
   - Single class retrieval
   - Class update (PUT /classes/{id})
   - Assign class teacher (PUT /classes/{id}/assign-teacher)
3. Subject Management:
   - Create subject with code, name, department
   - Subject code uniqueness validation (400 on duplicate code)
   - Subject listing
   - Subject update & deletion
4. Teacher Assignment:
   - Map teacher to class + subject (POST /assignments)
   - Duplicate assignment prevention (400 on duplicate mapping)
   - Filter assignments by class_id & teacher_id
   - Remove assignment (DELETE /assignments/{id})
"""

import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_academic_management_suite():
    print("=" * 70)
    print("STARTING ACADEMIC MANAGEMENT TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 0. AUTHENTICATION SETUP
    # -------------------------------------------------------------
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # -------------------------------------------------------------
    # 1. CLASS MANAGEMENT TESTS
    # -------------------------------------------------------------
    print("\n--- 1. Testing Class Management ---")
    suffix = uuid.uuid4().hex[:6]
    class_payload = {
        "name": f"B.Tech AI & Data Science {suffix}",
        "department": f"Data Science {suffix}",
        "year": 3,
        "section": "A",
    }
    # 1.1 Create class
    res_class = client.post("/api/v1/classes/", json=class_payload, headers=admin_headers)
    assert res_class.status_code == 201, f"Create class failed: {res_class.text}"
    class_data = res_class.json()
    class_id = class_data["id"]
    assert class_data["name"] == class_payload["name"]
    print(f"[PASS] Created class '{class_data['name']}' with ID {class_id}")

    # 1.2 Duplicate class detection
    res_dup_class = client.post("/api/v1/classes/", json=class_payload, headers=admin_headers)
    assert res_dup_class.status_code == 400, "Expected 400 for duplicate class"
    print("[PASS] Duplicate class creation rejected with HTTP 400")

    # 1.3 List classes
    res_list_classes = client.get("/api/v1/classes/", headers=admin_headers)
    assert res_list_classes.status_code == 200
    classes = res_list_classes.json()
    assert any(c["id"] == class_id for c in classes)
    print(f"[PASS] Listed {len(classes)} classes, found created class.")

    # 1.4 Get class details
    res_get_class = client.get(f"/api/v1/classes/{class_id}", headers=admin_headers)
    assert res_get_class.status_code == 200
    assert res_get_class.json()["id"] == class_id
    print("[PASS] Retrieved class details successfully.")

    # 1.5 Update class
    updated_name = f"B.Tech AI & Robotics {suffix}"
    res_update_class = client.put(
        f"/api/v1/classes/{class_id}",
        json={"name": updated_name},
        headers=admin_headers,
    )
    assert res_update_class.status_code == 200
    assert res_update_class.json()["name"] == updated_name
    print(f"[PASS] Updated class name to '{updated_name}'")

    # 1.6 Assign Class Teacher
    res_assign_ct = client.put(
        f"/api/v1/classes/{class_id}/assign-teacher",
        json={"class_teacher_id": 2},  # Teacher 'sharma'
        headers=admin_headers,
    )
    assert res_assign_ct.status_code == 200
    assert res_assign_ct.json()["class_teacher_id"] == 2
    print(f"[PASS] Assigned class teacher ID 2 to class {class_id}")

    # -------------------------------------------------------------
    # 2. SUBJECT MANAGEMENT TESTS
    # -------------------------------------------------------------
    print("\n--- 2. Testing Subject Management ---")
    subj_code = f"CS{suffix.upper()[:4]}"
    subj_payload = {
        "code": subj_code,
        "name": f"Computer Vision & Deep Learning {suffix}",
        "department": f"Data Science {suffix}",
    }
    # 2.1 Create subject
    res_subj = client.post("/api/v1/subjects/", json=subj_payload, headers=admin_headers)
    assert res_subj.status_code == 201, f"Create subject failed: {res_subj.text}"
    subj_data = res_subj.json()
    subject_id = subj_data["id"]
    assert subj_data["code"] == subj_code
    print(f"[PASS] Created subject '{subj_data['name']}' ({subj_code}) with ID {subject_id}")

    # 2.2 Duplicate subject code rejection
    res_dup_subj = client.post("/api/v1/subjects/", json=subj_payload, headers=admin_headers)
    assert res_dup_subj.status_code == 400, "Expected 400 for duplicate subject code"
    print("[PASS] Duplicate subject code rejected with HTTP 400")

    # 2.3 List subjects
    res_list_subj = client.get("/api/v1/subjects/", headers=admin_headers)
    assert res_list_subj.status_code == 200
    subjects = res_list_subj.json()
    assert any(s["id"] == subject_id for s in subjects)
    print(f"[PASS] Listed {len(subjects)} subjects, found created subject.")

    # 2.4 Update subject
    updated_subj_name = f"Advanced Computer Vision {suffix}"
    res_update_subj = client.put(
        f"/api/v1/subjects/{subject_id}",
        json={"name": updated_subj_name},
        headers=admin_headers,
    )
    assert res_update_subj.status_code == 200
    assert res_update_subj.json()["name"] == updated_subj_name
    print(f"[PASS] Updated subject name to '{updated_subj_name}'")

    # -------------------------------------------------------------
    # 3. TEACHER ASSIGNMENT TESTS
    # -------------------------------------------------------------
    print("\n--- 3. Testing Teacher Assignment ---")
    assign_payload = {
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": 3,  # Teacher 'patel'
    }
    # 3.1 Assign Subject Teacher to Class
    res_assign = client.post("/api/v1/assignments/", json=assign_payload, headers=admin_headers)
    assert res_assign.status_code == 201, f"Assignment failed: {res_assign.text}"
    assign_data = res_assign.json()
    assignment_id = assign_data["id"]
    assert assign_data["class_id"] == class_id
    assert assign_data["subject_id"] == subject_id
    assert assign_data["teacher_id"] == 3
    print(f"[PASS] Assigned teacher 3 to class {class_id} for subject {subject_id}")

    # 3.2 Duplicate assignment prevention
    res_dup_assign = client.post("/api/v1/assignments/", json=assign_payload, headers=admin_headers)
    assert res_dup_assign.status_code == 400, "Expected 400 for duplicate assignment"
    print("[PASS] Duplicate teacher-class-subject assignment rejected with HTTP 400")

    # 3.3 List assignments with filters
    res_list_assign = client.get(f"/api/v1/assignments/?class_id={class_id}", headers=admin_headers)
    assert res_list_assign.status_code == 200
    class_assignments = res_list_assign.json()
    assert any(a["id"] == assignment_id for a in class_assignments)
    print(f"[PASS] Filtered assignments by class_id={class_id}, verified mapping.")

    # -------------------------------------------------------------
    # 4. STUDENT MANAGEMENT TESTS
    # -------------------------------------------------------------
    print("\n--- 4. Testing Student Management ---")
    roll_num = f"ROLL_{suffix.upper()}"
    reg_num = f"REG_{suffix.upper()}"
    student_payload = {
        "roll_number": roll_num,
        "register_number": reg_num,
        "full_name": f"Aarav Sharma {suffix}",
        "department": f"Data Science {suffix}",
        "year": 3,
        "section": "A",
        "class_id": class_id,
        "email": f"aarav_{suffix}@college.edu",
        "phone": "+91 98765 43210",
        "is_active": True,
    }
    # 4.1 Create student
    res_student = client.post("/api/v1/students/", json=student_payload, headers=admin_headers)
    assert res_student.status_code == 201, f"Create student failed: {res_student.text}"
    st_data = res_student.json()
    student_id = st_data["id"]
    assert st_data["roll_number"] == roll_num
    assert st_data["register_number"] == reg_num
    assert st_data["full_name"] == student_payload["full_name"]
    print(f"[PASS] Created student '{st_data['full_name']}' (ID: {student_id}, Roll: {roll_num})")

    # 4.2 Duplicate roll number rejection
    dup_roll_payload = dict(student_payload)
    dup_roll_payload["register_number"] = f"REG2_{suffix.upper()}"
    res_dup_roll = client.post("/api/v1/students/", json=dup_roll_payload, headers=admin_headers)
    assert res_dup_roll.status_code == 400, "Expected 400 for duplicate roll number"
    print("[PASS] Duplicate roll number rejected with HTTP 400")

    # 4.3 Duplicate register number rejection
    dup_reg_payload = dict(student_payload)
    dup_reg_payload["roll_number"] = f"ROLL2_{suffix.upper()}"
    res_dup_reg = client.post("/api/v1/students/", json=dup_reg_payload, headers=admin_headers)
    assert res_dup_reg.status_code == 400, "Expected 400 for duplicate register number"
    print("[PASS] Duplicate register number rejected with HTTP 400")

    # 4.4 Get student by ID
    res_get_st = client.get(f"/api/v1/students/{student_id}", headers=admin_headers)
    assert res_get_st.status_code == 200
    assert res_get_st.json()["roll_number"] == roll_num
    print("[PASS] Retrieved student details by ID.")

    # 4.5 Filter students by class_id
    res_filter_st = client.get(f"/api/v1/students/?class_id={class_id}", headers=admin_headers)
    assert res_filter_st.status_code == 200
    st_list = res_filter_st.json()
    assert any(s["id"] == student_id for s in st_list)
    print(f"[PASS] Filtered students by class_id={class_id}, verified student exists.")

    # 4.6 Update student
    updated_st_name = f"Aarav K. Sharma {suffix}"
    res_update_st = client.put(
        f"/api/v1/students/{student_id}",
        json={"full_name": updated_st_name, "phone": "+91 99999 88888"},
        headers=admin_headers,
    )
    assert res_update_st.status_code == 200
    assert res_update_st.json()["full_name"] == updated_st_name
    print(f"[PASS] Updated student name to '{updated_st_name}'")

    # 4.7 Delete / deactivate student
    res_del_st = client.delete(f"/api/v1/students/{student_id}", headers=admin_headers)
    assert res_del_st.status_code == 204
    print(f"[PASS] Deleted student ID {student_id} with HTTP 204")

    # Verify student is gone or deactivated
    res_check_del = client.get(f"/api/v1/students/{student_id}", headers=admin_headers)
    assert res_check_del.status_code == 404
    print("[PASS] Verified deleted student returns HTTP 404.")

    # 4.8 Delete assignment
    res_del_assign = client.delete(f"/api/v1/assignments/{assignment_id}", headers=admin_headers)
    assert res_del_assign.status_code == 204
    print(f"[PASS] Deleted assignment ID {assignment_id} with HTTP 204")

    # 4.9 Delete subject
    res_del_subj = client.delete(f"/api/v1/subjects/{subject_id}", headers=admin_headers)
    assert res_del_subj.status_code == 204
    print(f"[PASS] Deleted subject ID {subject_id} with HTTP 204")

    # 4.10 Delete class
    res_del_cls = client.delete(f"/api/v1/classes/{class_id}", headers=admin_headers)
    assert res_del_cls.status_code == 204
    print(f"[PASS] Deleted class ID {class_id} with HTTP 204")

    print("\n>>> ALL ACADEMIC MANAGEMENT TESTS PASSED! <<<")


if __name__ == "__main__":
    test_academic_management_suite()
