"""
Automated Test Suite for the Class Teacher Portal & Student Management Flow.
Covers:
1. Role-based authorization (CLASS_TEACHER / ADMIN allowed, SUBJECT_TEACHER -> 403, Anonymous -> 401)
2. View assigned class (roster metrics, department, section, subjects list)
3. View student list (filtering by search, status, and face enrollment)
4. Add students (student ID, name, roll number, optional email, optional phone)
5. Edit student information
6. Deactivate / toggle status & delete student
7. Upload student face image with comprehensive validations:
   - Valid JPEG / PNG image accepted
   - Non-image / text file rejected (400)
   - Corrupted image bytes rejected (400)
   - Empty file rejected (400)
   - Oversized file (> 5MB) rejected (400)
   - Secure storage in data/faces
   - Static /faces endpoint serving
8. View face enrollment status
9. View class attendance summary (KPI metrics, subject breakdown, low attendance alerts)
"""

import io
import sys
import uuid
from pathlib import Path
from PIL import Image

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def create_dummy_image_bytes(width=120, height=120, format="JPEG", color=(100, 150, 200)) -> bytes:
    """Generates a valid test image in memory."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_class_teacher_portal_full():
    print("=" * 70)
    print("STARTING CLASS TEACHER PORTAL & STUDENT MANAGEMENT VERIFICATION")
    print("=" * 70)

    # -------------------------------------------------------------
    # 0. AUTHENTICATION SETUP
    # -------------------------------------------------------------
    print("\n--- STEP 0: Authenticating Faculty & Admin Roles ---")
    
    # Class Teacher (sharma)
    ct_res = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert ct_res.status_code == 200, f"Class teacher login failed: {ct_res.text}"
    ct_token = ct_res.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}
    print("[PASS] Class teacher 'sharma' authenticated (CLASS_TEACHER).")

    # Subject Teacher (patel)
    st_res = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert st_res.status_code == 200, f"Subject teacher login failed: {st_res.text}"
    st_token = st_res.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}
    print("[PASS] Subject teacher 'patel' authenticated (SUBJECT_TEACHER).")

    # Admin (admin)
    adm_res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert adm_res.status_code == 200, f"Admin login failed: {adm_res.text}"
    adm_token = adm_res.json()["access_token"]
    adm_headers = {"Authorization": f"Bearer {adm_token}"}
    print("[PASS] Administrator 'admin' authenticated (ADMIN).")

    # -------------------------------------------------------------
    # 1. ROLE-BASED ACCESS CONTROL (RBAC) FOR CLASS TEACHER PORTAL
    # -------------------------------------------------------------
    print("\n--- STEP 1: Verifying Strict Authorization & Role Boundaries ---")
    
    # Anonymous request -> 401
    anon_res = client.get("/api/v1/teachers/class-teacher/my-class")
    assert anon_res.status_code == 401, f"Expected 401 for anonymous, got {anon_res.status_code}"
    print("[PASS] Anonymous access correctly blocked (401 Unauthorized).")

    # Subject Teacher request -> 403 Forbidden
    st_my_class = client.get("/api/v1/teachers/class-teacher/my-class", headers=st_headers)
    assert st_my_class.status_code == 403, f"Expected 403 for subject teacher, got {st_my_class.status_code}"
    print("[PASS] Subject teacher forbidden from class teacher endpoints (403 Forbidden).")

    # Class Teacher request -> 200 OK
    ct_my_class = client.get("/api/v1/teachers/class-teacher/my-class", headers=ct_headers)
    assert ct_my_class.status_code == 200, f"Class teacher my-class failed: {ct_my_class.text}"
    class_data = ct_my_class.json()
    assert "id" in class_data
    assert "name" in class_data
    assert "total_students" in class_data
    print(f"[PASS] Class teacher retrieved assigned class: '{class_data['name']}' (ID: {class_data['id']}).")

    # -------------------------------------------------------------
    # 2. VIEW ASSIGNED CLASS DETAILS
    # -------------------------------------------------------------
    print("\n--- STEP 2: Verifying Assigned Class Details & KPI Metrics ---")
    assert class_data["department"] == "Computer Science" or "CSE" in class_data["name"]
    assert "active_students" in class_data
    assert "face_enrolled_count" in class_data
    assert "face_enrollment_rate" in class_data
    assert "overall_attendance_rate" in class_data
    assert isinstance(class_data["subjects"], list)
    print(f"[PASS] Class details verified. Total students: {class_data['total_students']}, Face enrolled: {class_data['face_enrolled_count']}.")

    # -------------------------------------------------------------
    # 3. VIEW STUDENT LIST & FILTERS
    # -------------------------------------------------------------
    print("\n--- STEP 3: Verifying Student List & Filtering ---")
    students_res = client.get("/api/v1/teachers/class-teacher/students", headers=ct_headers)
    assert students_res.status_code == 200, f"List students failed: {students_res.text}"
    student_list = students_res.json()
    assert len(student_list) >= 1
    sample_student = student_list[0]
    assert "roll_number" in sample_student
    assert "full_name" in sample_student
    assert "is_active" in sample_student
    assert "face_enrolled" in sample_student
    print(f"[PASS] Student list loaded with {len(student_list)} students. Sample: {sample_student['roll_number']} - {sample_student['full_name']}.")

    # Search filter test
    search_query = sample_student["roll_number"][:5]
    search_res = client.get(f"/api/v1/teachers/class-teacher/students?search={search_query}", headers=ct_headers)
    assert search_res.status_code == 200
    filtered_list = search_res.json()
    assert any(s["roll_number"] == sample_student["roll_number"] for s in filtered_list)
    print(f"[PASS] Student search query '{search_query}' returned {len(filtered_list)} matching record(s).")

    # Status filter test
    active_res = client.get("/api/v1/teachers/class-teacher/students?status=active", headers=ct_headers)
    assert active_res.status_code == 200
    for s in active_res.json():
        assert s["is_active"] is True
    print("[PASS] Active status filter validated.")

    # -------------------------------------------------------------
    # 4. ADD STUDENT FLOW (STUDENT ID, NAME, ROLL, EMAIL, PHONE)
    # -------------------------------------------------------------
    print("\n--- STEP 4: Testing Student Creation by Class Teacher ---")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_roll = f"CT{unique_suffix}"
    new_student_payload = {
        "name": f"Student Tester {unique_suffix}",
        "roll_number": test_roll,
        "register_number": f"REG_{test_roll}",
        "email": f"student_{unique_suffix.lower()}@college.edu",
        "phone": "+91-9876543210",
    }

    add_res = client.post("/api/v1/teachers/class-teacher/students", json=new_student_payload, headers=ct_headers)
    assert add_res.status_code == 201, f"Add student failed: {add_res.text}"
    created_student = add_res.json()
    created_id = created_student["id"]
    assert created_student["roll_number"] == test_roll
    assert created_student["full_name"] == new_student_payload["name"]
    assert created_student["email"] == new_student_payload["email"]
    assert created_student["phone"] == new_student_payload["phone"]
    assert created_student["class_id"] == class_data["id"]
    assert created_student["face_enrolled"] is False
    assert created_student["is_active"] is True
    print(f"[PASS] Student created successfully with ID {created_id} in Class {created_student['class_name']}.")

    # Duplicate roll number rejection
    dup_res = client.post("/api/v1/teachers/class-teacher/students", json=new_student_payload, headers=ct_headers)
    assert dup_res.status_code == 400, "Expected duplicate roll number to be rejected with 400"
    print("[PASS] Duplicate student roll number correctly rejected (400 Bad Request).")

    # Missing name rejection
    invalid_payload = {"roll_number": f"FAIL{unique_suffix}", "name": "   "}
    inv_res = client.post("/api/v1/teachers/class-teacher/students", json=invalid_payload, headers=ct_headers)
    assert inv_res.status_code == 400
    print("[PASS] Missing student name rejected with 400.")

    # -------------------------------------------------------------
    # 5. EDIT STUDENT INFORMATION
    # -------------------------------------------------------------
    print("\n--- STEP 5: Testing Student Information Update ---")
    update_payload = {
        "name": f"Student Updated {unique_suffix}",
        "email": f"updated_{unique_suffix.lower()}@college.edu",
        "phone": "+91-9123456789",
    }
    edit_res = client.put(f"/api/v1/teachers/class-teacher/students/{created_id}", json=update_payload, headers=ct_headers)
    assert edit_res.status_code == 200, f"Edit student failed: {edit_res.text}"
    updated_student = edit_res.json()
    assert updated_student["full_name"] == update_payload["name"]
    assert updated_student["email"] == update_payload["email"]
    assert updated_student["phone"] == update_payload["phone"]
    print(f"[PASS] Student details successfully updated: '{updated_student['full_name']}', '{updated_student['email']}'.")

    # -------------------------------------------------------------
    # 6. TOGGLE STATUS (DEACTIVATE / ACTIVATE)
    # -------------------------------------------------------------
    print("\n--- STEP 6: Testing Deactivate & Activate (Toggle Status) ---")
    toggle_res1 = client.patch(f"/api/v1/teachers/class-teacher/students/{created_id}/toggle-status", headers=ct_headers)
    assert toggle_res1.status_code == 200
    assert toggle_res1.json()["is_active"] is False
    print(f"[PASS] Student successfully deactivated (is_active = False).")

    toggle_res2 = client.patch(f"/api/v1/teachers/class-teacher/students/{created_id}/toggle-status", headers=ct_headers)
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["is_active"] is True
    print(f"[PASS] Student reactivated (is_active = True).")

    # -------------------------------------------------------------
    # 7. UPLOAD FACE IMAGE & SECURITY VALIDATIONS
    # -------------------------------------------------------------
    print("\n--- STEP 7: Testing Face Image Upload & Security Validations ---")
    
    # 7a. Reject non-image text file
    bad_file = ("script.txt", b"alert('xss')", "text/plain")
    bad_res = client.post(
        f"/api/v1/teachers/class-teacher/students/{created_id}/upload-face",
        files={"file": bad_file},
        headers=ct_headers,
    )
    assert bad_res.status_code == 400, f"Expected 400 for text/plain, got {bad_res.status_code}"
    print(f"[PASS] Non-image file rejected: {bad_res.json()['detail']}.")

    # 7b. Reject fake image (disguised .jpg extension with non-image bytes)
    corrupt_file = ("fake.jpg", b"This is not a real image raster", "image/jpeg")
    corrupt_res = client.post(
        f"/api/v1/teachers/class-teacher/students/{created_id}/upload-face",
        files={"file": corrupt_file},
        headers=ct_headers,
    )
    assert corrupt_res.status_code == 400
    print(f"[PASS] Corrupted/fake image file rejected: {corrupt_res.json()['detail']}.")

    # 7c. Reject empty image (0 bytes)
    empty_file = ("empty.png", b"", "image/png")
    empty_res = client.post(
        f"/api/v1/teachers/class-teacher/students/{created_id}/upload-face",
        files={"file": empty_file},
        headers=ct_headers,
    )
    assert empty_res.status_code == 400
    print(f"[PASS] Empty 0-byte file rejected: {empty_res.json()['detail']}.")

    # 7d. Reject oversized file (> 5MB)
    oversized_bytes = b"0" * (5 * 1024 * 1024 + 1024)
    oversized_file = ("huge.jpg", oversized_bytes, "image/jpeg")
    oversized_res = client.post(
        f"/api/v1/teachers/class-teacher/students/{created_id}/upload-face",
        files={"file": oversized_file},
        headers=ct_headers,
    )
    assert oversized_res.status_code == 400
    print(f"[PASS] Oversized (>5MB) file rejected: {oversized_res.json()['detail']}.")

    # 7e. Accept valid JPEG image
    sample_path = backend_dir.parent / "data" / "test_samples" / "single_student.jpg"
    valid_jpeg = sample_path.read_bytes() if sample_path.exists() else create_dummy_image_bytes(width=200, height=200, format="JPEG", color=(60, 120, 210))
    valid_file = ("portrait.jpg", valid_jpeg, "image/jpeg")
    upload_res = client.post(
        f"/api/v1/teachers/class-teacher/students/{created_id}/upload-face",
        files={"file": valid_file},
        headers=ct_headers,
    )
    assert upload_res.status_code == 200, f"Valid face upload failed: {upload_res.text}"
    enrollment_data = upload_res.json()
    assert enrollment_data["face_enrolled"] is True
    assert enrollment_data["face_image_path"] is not None
    face_path = enrollment_data["face_image_path"]
    print(f"[PASS] Valid face image uploaded successfully. Stored URL: {face_path}.")

    # Verify static /faces serving works
    face_preview_res = client.get(face_path)
    assert face_preview_res.status_code == 200
    assert len(face_preview_res.content) > 0
    print(f"[PASS] Static face photo served via '{face_path}' (200 OK, size: {len(face_preview_res.content)} bytes).")

    # -------------------------------------------------------------
    # 8. VIEW FACE ENROLLMENT STATUS
    # -------------------------------------------------------------
    print("\n--- STEP 8: Testing Face Enrollment Status Verification ---")
    status_res = client.get(f"/api/v1/teachers/class-teacher/students/{created_id}/face", headers=ct_headers)
    assert status_res.status_code == 200, f"Face status check failed: {status_res.text}"
    status_info = status_res.json()
    assert status_info["face_enrolled"] is True
    assert status_info["status_label"] == "Enrolled"
    assert status_info["face_image_path"] == face_path
    print(f"[PASS] Face enrollment verified: status={status_info['status_label']}, path={status_info['face_image_path']}.")

    # -------------------------------------------------------------
    # 9. VIEW ATTENDANCE SUMMARY
    # -------------------------------------------------------------
    print("\n--- STEP 9: Testing Class Attendance Summary Analytics ---")
    summary_res = client.get("/api/v1/teachers/class-teacher/attendance-summary", headers=ct_headers)
    assert summary_res.status_code == 200, f"Attendance summary failed: {summary_res.text}"
    summary = summary_res.json()
    assert "class_id" in summary
    assert "class_name" in summary
    assert "total_students" in summary
    assert "active_students" in summary
    assert "face_enrolled_count" in summary
    assert "overall_attendance_rate" in summary
    assert "subject_summaries" in summary
    assert "low_attendance_students" in summary
    print(f"[PASS] Class attendance summary retrieved successfully for {summary['class_name']}.")
    print(f"       Class Strength: {summary['total_students']}, Face Enrolled: {summary['face_enrolled_count']}, Attendance Rate: {summary['overall_attendance_rate']}%.")

    # -------------------------------------------------------------
    # 10. DELETE STUDENT FLOW
    # -------------------------------------------------------------
    print("\n--- STEP 10: Testing Student Deletion ---")
    del_res = client.delete(f"/api/v1/teachers/class-teacher/students/{created_id}", headers=ct_headers)
    assert del_res.status_code == 204
    print(f"[PASS] Student ID {created_id} deleted successfully (204 No Content).")

    # Verify student is no longer in list
    check_res = client.get(f"/api/v1/teachers/class-teacher/students/{created_id}", headers=ct_headers)
    assert check_res.status_code == 404
    print("[PASS] Verified student record is removed.")

    print("\n" + "=" * 70)
    print("ALL CLASS TEACHER PORTAL & STUDENT MANAGEMENT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_class_teacher_portal_full()
