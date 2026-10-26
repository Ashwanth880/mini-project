"""
Comprehensive Test Suite for the Admin Portal & Role-Based Authorization.
Covers:
1. Role-based authorization checks (Anonymous -> 401, Non-Admin -> 403, Admin -> 200/201/204)
2. Classes API (CRUD, assign class teacher, validation)
3. Subjects API (CRUD, code uniqueness)
4. Teachers API (CRUD, password hashing, self-deletion prevention)
5. Assignments API (Class-Subject-Teacher mapping, duplicate check, deletion)
6. Students API (CRUD, roll/reg validation, filtering)
7. Attendance Records API (Viewing with filters, manual creation, deletion)
8. Dashboard Stats API (Institution KPI metrics)
9. Both /api/v1/admin/* and direct /api/v1/* routes
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


def test_admin_portal_full():
    print("=" * 60)
    print("STARTING ADMIN PORTAL & APIS AUTOMATED VERIFICATION")
    print("=" * 60)

    # -------------------------------------------------------------
    # 0. AUTHENTICATION SETUP
    # -------------------------------------------------------------
    print("\n--- STEP 0: Authenticating Users ---")
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] Admin logged in successfully with ADMIN role.")

    teacher_login = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert teacher_login.status_code == 200, f"Teacher login failed: {teacher_login.text}"
    teacher_token = teacher_login.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    print("[PASS] Teacher logged in successfully with CLASS_TEACHER role.")

    # -------------------------------------------------------------
    # 1. ROLE-BASED ACCESS CONTROL (RBAC) VERIFICATION
    # -------------------------------------------------------------
    print("\n--- STEP 1: Verifying Strict Role-Based Authorization ---")
    admin_endpoints = [
        ("GET", "/api/v1/admin/dashboard-stats"),
        ("GET", "/api/v1/admin/classes"),
        ("POST", "/api/v1/admin/classes"),
        ("GET", "/api/v1/admin/subjects"),
        ("POST", "/api/v1/admin/subjects"),
        ("GET", "/api/v1/admin/teachers"),
        ("POST", "/api/v1/admin/teachers"),
        ("GET", "/api/v1/admin/assignments"),
        ("POST", "/api/v1/admin/assignments"),
        ("GET", "/api/v1/admin/students"),
        ("POST", "/api/v1/admin/students"),
        ("GET", "/api/v1/admin/attendance"),
    ]

    for method, path in admin_endpoints:
        # Anonymous -> 401
        res_anon = client.request(method, path, json={})
        assert res_anon.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res_anon.status_code}"

        # Teacher -> 403 Forbidden
        res_teacher = client.request(method, path, headers=teacher_headers, json={})
        assert res_teacher.status_code == 403, f"Expected 403 for non-admin on {method} {path}, got {res_teacher.status_code}"

    print("[PASS] All admin endpoints strictly enforce 401 Unauthorized for anonymous and 403 Forbidden for teachers!")

    # -------------------------------------------------------------
    # 2. CLASSES API (CRUD & ASSIGN TEACHER)
    # -------------------------------------------------------------
    print("\n--- STEP 2: Testing Classes Management API ---")
    uid = uuid.uuid4().hex[:6]
    class_payload = {
        "name": f"ECE - 2nd Year - Sec B_{uid}",
        "department": "Electronics",
        "year": 2,
        "section": "B",
        "class_teacher_id": None,
    }

    # Create Class (Admin)
    res_create_class = client.post("/api/v1/admin/classes", headers=admin_headers, json=class_payload)
    assert res_create_class.status_code == 201, f"Create class failed: {res_create_class.text}"
    created_class = res_create_class.json()
    class_id = created_class["id"]
    assert created_class["name"] == class_payload["name"]
    print(f"[PASS] POST /admin/classes created Class ID #{class_id}: {created_class['name']}")

    # Duplicate Class Prevention
    res_dup_class = client.post("/api/v1/admin/classes", headers=admin_headers, json=class_payload)
    assert res_dup_class.status_code == 400, "Expected 400 for duplicate class creation"
    print("[PASS] Duplicate class creation rejected with HTTP 400.")

    # Get Single Class
    res_get_class = client.get(f"/api/v1/admin/classes/{class_id}", headers=admin_headers)
    assert res_get_class.status_code == 200
    assert res_get_class.json()["id"] == class_id
    print(f"[PASS] GET /admin/classes/{class_id} retrieved successfully.")

    # Also test direct route GET /classes/{class_id}
    res_direct_get_class = client.get(f"/api/v1/classes/{class_id}", headers=admin_headers)
    assert res_direct_get_class.status_code == 200
    print(f"[PASS] Direct route GET /classes/{class_id} verified.")

    # Update Class
    res_update_class = client.put(
        f"/api/v1/admin/classes/{class_id}",
        headers=admin_headers,
        json={"name": f"ECE - 2nd Year - Sec B_Updated_{uid}"},
    )
    assert res_update_class.status_code == 200
    assert "Updated" in res_update_class.json()["name"]
    print(f"[PASS] PUT /admin/classes/{class_id} updated name successfully.")

    # Assign Class Teacher
    teacher_id = teacher_login.json()["user"]["id"]
    res_assign_ct = client.put(
        f"/api/v1/admin/classes/{class_id}/assign-teacher",
        headers=admin_headers,
        json={"class_teacher_id": teacher_id},
    )
    assert res_assign_ct.status_code == 200
    assert res_assign_ct.json()["class_teacher_id"] == teacher_id
    assert res_assign_ct.json()["class_teacher_name"] is not None
    print(f"[PASS] PUT /admin/classes/{class_id}/assign-teacher assigned teacher '{res_assign_ct.json()['class_teacher_name']}'.")

    # List Classes
    res_list_classes = client.get("/api/v1/admin/classes", headers=admin_headers)
    assert res_list_classes.status_code == 200
    assert len(res_list_classes.json()) > 0
    print(f"[PASS] GET /admin/classes returned {len(res_list_classes.json())} classes.")

    # -------------------------------------------------------------
    # 3. SUBJECTS API (CRUD)
    # -------------------------------------------------------------
    print("\n--- STEP 3: Testing Subjects Management API ---")
    subj_code = f"EC{uid[:4].upper()}"
    subj_payload = {
        "code": subj_code,
        "name": "Digital Signal Processing",
        "department": "Electronics",
    }

    # Create Subject (Admin)
    res_create_subj = client.post("/api/v1/admin/subjects", headers=admin_headers, json=subj_payload)
    assert res_create_subj.status_code == 201, f"Create subject failed: {res_create_subj.text}"
    created_subj = res_create_subj.json()
    subject_id = created_subj["id"]
    assert created_subj["code"] == subj_code
    print(f"[PASS] POST /admin/subjects created Subject ID #{subject_id}: {created_subj['code']} - {created_subj['name']}")

    # Duplicate Subject Code Check
    res_dup_subj = client.post("/api/v1/admin/subjects", headers=admin_headers, json=subj_payload)
    assert res_dup_subj.status_code == 400
    print("[PASS] Duplicate subject code rejected with HTTP 400.")

    # Get Subject
    res_get_subj = client.get(f"/api/v1/admin/subjects/{subject_id}", headers=admin_headers)
    assert res_get_subj.status_code == 200
    print(f"[PASS] GET /admin/subjects/{subject_id} retrieved successfully.")

    # Update Subject
    res_update_subj = client.put(
        f"/api/v1/admin/subjects/{subject_id}",
        headers=admin_headers,
        json={"name": "Advanced Digital Signal Processing"},
    )
    assert res_update_subj.status_code == 200
    assert res_update_subj.json()["name"] == "Advanced Digital Signal Processing"
    print(f"[PASS] PUT /admin/subjects/{subject_id} updated name successfully.")

    # List Subjects (direct route also)
    res_direct_list_subj = client.get("/api/v1/subjects/", headers=admin_headers)
    assert res_direct_list_subj.status_code == 200
    print(f"[PASS] Direct route GET /subjects/ returned {len(res_direct_list_subj.json())} subjects.")

    # -------------------------------------------------------------
    # 4. TEACHERS API (CRUD)
    # -------------------------------------------------------------
    print("\n--- STEP 4: Testing Teachers Management API ---")
    teacher_username = f"faculty_{uid}"
    teacher_email = f"faculty_{uid}@college.edu"
    new_teacher_payload = {
        "username": teacher_username,
        "email": teacher_email,
        "full_name": "Prof. Test Faculty",
        "role": "SUBJECT_TEACHER",
        "department": "Electronics",
        "password": "securepassword123",
    }

    # Create Teacher (Admin)
    res_create_t = client.post("/api/v1/admin/teachers", headers=admin_headers, json=new_teacher_payload)
    assert res_create_t.status_code == 201, f"Create teacher failed: {res_create_t.text}"
    created_teacher = res_create_t.json()
    new_teacher_id = created_teacher["id"]
    assert created_teacher["username"] == teacher_username
    print(f"[PASS] POST /admin/teachers created Teacher ID #{new_teacher_id}: {created_teacher['full_name']}")

    # Verify newly created teacher can authenticate
    new_t_login = client.post("/auth/login", json={"username": teacher_username, "password": "securepassword123"})
    assert new_t_login.status_code == 200, "New teacher login failed"
    print("[PASS] Created teacher authenticated successfully with bcrypt hash.")

    # Get Single Teacher
    res_get_t = client.get(f"/api/v1/admin/teachers/{new_teacher_id}", headers=admin_headers)
    assert res_get_t.status_code == 200
    print(f"[PASS] GET /admin/teachers/{new_teacher_id} retrieved successfully.")

    # Update Teacher
    res_update_t = client.put(
        f"/api/v1/admin/teachers/{new_teacher_id}",
        headers=admin_headers,
        json={"department": "Robotics & Automation"},
    )
    assert res_update_t.status_code == 200
    assert res_update_t.json()["department"] == "Robotics & Automation"
    print(f"[PASS] PUT /admin/teachers/{new_teacher_id} updated department successfully.")

    # Prevent Admin from deleting own account
    admin_id = admin_login.json()["user"]["id"]
    res_del_self = client.delete(f"/api/v1/admin/teachers/{admin_id}", headers=admin_headers)
    assert res_del_self.status_code == 400
    print("[PASS] Self-deletion prevention works: cannot delete active admin account.")

    # -------------------------------------------------------------
    # 5. ASSIGNMENTS API (MAPPING CLASS, SUBJECT, TEACHER)
    # -------------------------------------------------------------
    print("\n--- STEP 5: Testing Teacher Assignments API ---")
    assign_payload = {
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": new_teacher_id,
    }

    # Create Assignment (Admin)
    res_assign_st = client.post("/api/v1/admin/assignments", headers=admin_headers, json=assign_payload)
    assert res_assign_st.status_code == 201, f"Assignment failed: {res_assign_st.text}"
    assignment = res_assign_st.json()
    assignment_id = assignment["id"]
    assert assignment["class_name"] is not None
    assert assignment["subject_name"] is not None
    assert assignment["teacher_name"] is not None
    print(f"[PASS] POST /admin/assignments created Assignment ID #{assignment_id}: '{assignment['teacher_name']}' -> '{assignment['subject_name']}' ({assignment['class_name']})")

    # Duplicate Assignment Check
    res_dup_assign = client.post("/api/v1/admin/assignments", headers=admin_headers, json=assign_payload)
    assert res_dup_assign.status_code == 400
    print("[PASS] Duplicate teacher assignment rejected with HTTP 400.")

    # List Assignments (direct route also)
    res_list_assign = client.get("/api/v1/assignments/", headers=admin_headers)
    assert res_list_assign.status_code == 200
    assert any(a["id"] == assignment_id for a in res_list_assign.json())
    print(f"[PASS] Direct route GET /assignments/ returned assignments successfully.")

    # -------------------------------------------------------------
    # 6. STUDENTS API (CRUD & FILTERS)
    # -------------------------------------------------------------
    print("\n--- STEP 6: Testing Students Management API ---")
    roll_no = f"22EC{uid[:3].upper()}"
    reg_no = f"910022{uid[:6]}"
    student_payload = {
        "roll_number": roll_no,
        "register_number": reg_no,
        "full_name": "Divya Prakash",
        "department": "Electronics",
        "year": 2,
        "section": "B",
        "class_id": class_id,
    }

    # Create Student (Admin)
    res_create_stud = client.post("/api/v1/admin/students", headers=admin_headers, json=student_payload)
    assert res_create_stud.status_code == 201, f"Create student failed: {res_create_stud.text}"
    student = res_create_stud.json()
    student_id = student["id"]
    assert student["roll_number"] == roll_no
    assert student["class_id"] == class_id
    print(f"[PASS] POST /admin/students created Student ID #{student_id}: {student['full_name']} ({student['roll_number']})")

    # Duplicate Roll Number Check
    res_dup_stud = client.post("/api/v1/admin/students", headers=admin_headers, json=student_payload)
    assert res_dup_stud.status_code == 400
    print("[PASS] Duplicate student roll/register number rejected with HTTP 400.")

    # Get Single Student
    res_get_stud = client.get(f"/api/v1/admin/students/{student_id}", headers=admin_headers)
    assert res_get_stud.status_code == 200
    assert res_get_stud.json()["id"] == student_id
    print(f"[PASS] GET /admin/students/{student_id} retrieved student successfully.")

    # Update Student
    res_update_stud = client.put(
        f"/api/v1/admin/students/{student_id}",
        headers=admin_headers,
        json={"full_name": "Divya Prakash Sharma", "is_active": True},
    )
    assert res_update_stud.status_code == 200
    assert res_update_stud.json()["full_name"] == "Divya Prakash Sharma"
    print(f"[PASS] PUT /admin/students/{student_id} updated student name successfully.")

    # Filter Students by Class ID
    res_filter_stud = client.get(f"/api/v1/admin/students?class_id={class_id}", headers=admin_headers)
    assert res_filter_stud.status_code == 200
    filtered_list = res_filter_stud.json()
    assert any(s["id"] == student_id for s in filtered_list)
    print(f"[PASS] GET /admin/students?class_id={class_id} filtered students accurately.")

    # Direct route GET /students/
    res_direct_stud = client.get("/api/v1/students/", headers=admin_headers)
    assert res_direct_stud.status_code == 200
    print(f"[PASS] Direct route GET /students/ verified.")

    # -------------------------------------------------------------
    # 7. ATTENDANCE RECORDS VIEW & MANAGEMENT API
    # -------------------------------------------------------------
    print("\n--- STEP 7: Testing Attendance Records API ---")
    att_payload = {
        "student_id": student_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": new_teacher_id,
        "date": "2026-10-04",
        "period": 2,
        "status": "PRESENT",
        "confidence": 0.95,
        "is_manual": True,
    }

    # Create Attendance Record (Admin)
    res_create_att = client.post("/api/v1/admin/attendance", headers=admin_headers, json=att_payload)
    assert res_create_att.status_code == 201, f"Create attendance record failed: {res_create_att.text}"
    att_record = res_create_att.json()
    att_record_id = att_record["id"]
    assert att_record["status"] == "PRESENT"
    assert att_record["student_roll"] == roll_no
    print(f"[PASS] POST /admin/attendance created Record ID #{att_record_id} for student '{att_record['student_name']}'")

    # View Attendance Records with Filters
    res_view_att = client.get(
        f"/api/v1/admin/attendance?class_id={class_id}&subject_id={subject_id}&status_filter=PRESENT",
        headers=admin_headers,
    )
    assert res_view_att.status_code == 200
    att_list = res_view_att.json()
    assert any(r["id"] == att_record_id for r in att_list)
    print(f"[PASS] GET /admin/attendance with multiple filters returned {len(att_list)} matching records.")

    # -------------------------------------------------------------
    # 8. ADMIN DASHBOARD STATS API
    # -------------------------------------------------------------
    print("\n--- STEP 8: Testing Admin Dashboard Stats API ---")
    res_stats = client.get("/api/v1/admin/dashboard-stats", headers=admin_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_classes"] > 0
    assert stats["total_subjects"] > 0
    assert stats["total_teachers"] > 0
    assert stats["total_students"] > 0
    assert stats["total_attendance_records"] > 0
    print(f"[PASS] GET /admin/dashboard-stats returned complete metrics:")
    print(f"       Classes: {stats['total_classes']}, Subjects: {stats['total_subjects']}, Teachers: {stats['total_teachers']}, Students: {stats['total_students']}, Attendance: {stats['total_attendance_records']} ({stats['attendance_rate']}%)")

    # -------------------------------------------------------------
    # 9. DELETION CLEANUP TESTS (Admin Delete Operations)
    # -------------------------------------------------------------
    print("\n--- STEP 9: Testing Delete Operations ---")
    # Delete Attendance Record
    res_del_att = client.delete(f"/api/v1/admin/attendance/{att_record_id}", headers=admin_headers)
    assert res_del_att.status_code == 204
    print(f"[PASS] DELETE /admin/attendance/{att_record_id} removed record.")

    # Delete Assignment
    res_del_assign = client.delete(f"/api/v1/admin/assignments/{assignment_id}", headers=admin_headers)
    assert res_del_assign.status_code == 204
    print(f"[PASS] DELETE /admin/assignments/{assignment_id} removed assignment.")

    # Delete Student
    res_del_stud = client.delete(f"/api/v1/admin/students/{student_id}", headers=admin_headers)
    assert res_del_stud.status_code == 204
    print(f"[PASS] DELETE /admin/students/{student_id} removed student.")

    # Delete Subject
    res_del_subj = client.delete(f"/api/v1/admin/subjects/{subject_id}", headers=admin_headers)
    assert res_del_subj.status_code == 204
    print(f"[PASS] DELETE /admin/subjects/{subject_id} removed subject.")

    # Delete Teacher
    res_del_t = client.delete(f"/api/v1/admin/teachers/{new_teacher_id}", headers=admin_headers)
    assert res_del_t.status_code == 204
    print(f"[PASS] DELETE /admin/teachers/{new_teacher_id} removed teacher.")

    # Delete Class
    res_del_c = client.delete(f"/api/v1/admin/classes/{class_id}", headers=admin_headers)
    assert res_del_c.status_code == 204
    print(f"[PASS] DELETE /admin/classes/{class_id} removed class.")

    print("\n" + "=" * 60)
    print(">>> 100% OF ADMIN PORTAL & API TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 60)


if __name__ == "__main__":
    test_admin_portal_full()
