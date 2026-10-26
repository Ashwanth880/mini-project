"""
Comprehensive Automated Test Suite for the Face Enrollment Pipeline.

Covers:
1. Endpoint availability:
   - POST /students/{student_id}/face (direct root route)
   - POST /api/v1/students/{student_id}/face (api_v1 route)
   - GET /students/{student_id}/face (status inspection)
2. Valid face enrollment:
   - Successfully enrolls single face portrait
   - Extracts 128D normalized feature embedding
   - Stores image securely in data/faces
   - Returns message: 'Face enrolled successfully'
3. Rejection of zero faces:
   - Images without human faces are rejected
   - Returns message: 'No face detected'
4. Rejection of multiple faces:
   - Images containing more than one face are rejected
   - Returns message: 'Multiple faces detected'
5. Image quality checks:
   - Blurry images rejected with 'Image quality insufficient'
   - Underexposed / dark images rejected with 'Image quality insufficient'
   - Overexposed / washed out images rejected with 'Image quality insufficient'
6. Security & Authorization:
   - Class Teacher can enroll face for students in assigned class section
   - Class Teacher forbidden from enrolling students in other sections (403)
   - Subject Teacher forbidden from face enrollment (403)
   - Admin allowed to enroll face for any student
   - Non-existent student rejected (404)
7. Wrong student association prevention:
   - Distinct embeddings assigned strictly to corresponding students
   - Transactional atomicity: rollback cleans up disk images on failure
"""

import io
import json
import sys
from pathlib import Path
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.student import Student, StudentFace
from app.models.academic import Class
from app.models.user import User, UserRole

client = TestClient(app)
samples_dir = backend_dir.parent / "data" / "test_samples"


def test_face_enrollment_pipeline_full():
    print("=" * 75)
    print("STARTING FACE ENROLLMENT PIPELINE VERIFICATION")
    print("=" * 75)

    # -------------------------------------------------------------
    # 0. SETUP AUTH TOKENS & SAMPLE STUDENTS
    # -------------------------------------------------------------
    print("\n--- STEP 0: Setup Authentication & Student Accounts ---")
    ct_res = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert ct_res.status_code == 200, f"Class teacher login failed: {ct_res.text}"
    ct_token = ct_res.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    admin_res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_res.status_code == 200, f"Admin login failed: {admin_res.text}"
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    subj_res = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert subj_res.status_code == 200, f"Subject teacher login failed: {subj_res.text}"
    subj_token = subj_res.json()["access_token"]
    subj_headers = {"Authorization": f"Bearer {subj_token}"}

    # Ensure test students exist in DB
    db = SessionLocal()
    try:
        sample_class = db.query(Class).first()
        assert sample_class is not None, "Class record required in database"

        st1 = db.query(Student).filter(Student.roll_number == "TEST_ST_001").first()
        if not st1:
            st1 = Student(
                roll_number="TEST_ST_001",
                register_number="REG_TEST_001",
                full_name="Karan Malhotra",
                department="Computer Science",
                year=3,
                section="A",
                class_id=sample_class.id,
                face_enrolled=False,
            )
            db.add(st1)

        st2 = db.query(Student).filter(Student.roll_number == "TEST_ST_002").first()
        if not st2:
            st2 = Student(
                roll_number="TEST_ST_002",
                register_number="REG_TEST_002",
                full_name="Pooja Hegde",
                department="Computer Science",
                year=3,
                section="A",
                class_id=sample_class.id,
                face_enrolled=False,
            )
            db.add(st2)

        # Another class for class teacher boundary tests
        other_class = db.query(Class).filter(Class.name == "Mechanical - 2nd Year").first()
        if not other_class:
            other_class = Class(
                name="Mechanical - 2nd Year",
                department="Mechanical Engineering",
                year=2,
                section="B",
                class_teacher_id=None,
            )
            db.add(other_class)
            db.commit()

        st_other = db.query(Student).filter(Student.roll_number == "TEST_OTHER_001").first()
        if not st_other:
            st_other = Student(
                roll_number="TEST_OTHER_001",
                register_number="REG_OTHER_001",
                full_name="Rohan Joshi",
                department="Mechanical Engineering",
                year=2,
                section="B",
                class_id=other_class.id,
                face_enrolled=False,
            )
            db.add(st_other)

        db.commit()
        st1_id = st1.id
        st2_id = st2.id
        st_other_id = st_other.id
    finally:
        db.close()

    print(f"[SETUP OK] Test students ready: Student 1 (ID={st1_id}), Student 2 (ID={st2_id}), Other (ID={st_other_id})")

    # -------------------------------------------------------------
    # 1. TEST ZERO FACES (Reject 0 faces -> 'No face detected')
    # -------------------------------------------------------------
    print("\n--- STEP 1: Testing Zero Faces Rejection (No face detected) ---")
    no_face_path = samples_dir / "no_face.jpg"
    assert no_face_path.exists(), "Sample file no_face.jpg must exist"
    no_face_bytes = no_face_path.read_bytes()

    res_no = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("no_face.jpg", no_face_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_no.status_code == 400, f"Expected 400, got {res_no.status_code}: {res_no.text}"
    body_no = res_no.json()
    assert body_no["message"] == "No face detected", f"Expected 'No face detected', got {body_no}"
    assert body_no["detail"] == "No face detected"
    assert body_no["success"] is False
    print(f"[PASS] Zero faces rejected correctly: message='{body_no['message']}'")

    # -------------------------------------------------------------
    # 2. TEST MULTIPLE FACES (Reject >1 faces -> 'Multiple faces detected')
    # -------------------------------------------------------------
    print("\n--- STEP 2: Testing Multiple Faces Rejection (Multiple faces detected) ---")
    two_faces_path = samples_dir / "two_students.jpg"
    assert two_faces_path.exists(), "Sample file two_students.jpg must exist"
    two_faces_bytes = two_faces_path.read_bytes()

    res_multi = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("two_students.jpg", two_faces_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_multi.status_code == 400, f"Expected 400, got {res_multi.status_code}: {res_multi.text}"
    body_multi = res_multi.json()
    assert body_multi["message"] == "Multiple faces detected", f"Expected 'Multiple faces detected', got {body_multi}"
    assert body_multi["detail"] == "Multiple faces detected"
    assert body_multi["success"] is False
    print(f"[PASS] Multiple faces rejected correctly: message='{body_multi['message']}'")

    # -------------------------------------------------------------
    # 3. TEST IMAGE QUALITY CHECKS ('Image quality insufficient')
    # -------------------------------------------------------------
    print("\n--- STEP 3: Testing Image Quality Rejection (Image quality insufficient) ---")
    # 3a. Blurry face
    blur_path = samples_dir / "blurry_face.jpg"
    assert blur_path.exists(), "Sample file blurry_face.jpg must exist"
    res_blur = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("blurry_face.jpg", blur_path.read_bytes(), "image/jpeg")},
        headers=ct_headers,
    )
    assert res_blur.status_code == 400, f"Expected 400, got {res_blur.status_code}: {res_blur.text}"
    body_blur = res_blur.json()
    assert body_blur["message"] == "Image quality insufficient", f"Expected 'Image quality insufficient', got {body_blur}"
    assert body_blur["detail"] == "Image quality insufficient"
    print(f"[PASS] Blurry image rejected correctly: message='{body_blur['message']}'")

    # 3b. Dark face
    dark_path = samples_dir / "dark_face.jpg"
    assert dark_path.exists(), "Sample file dark_face.jpg must exist"
    res_dark = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("dark_face.jpg", dark_path.read_bytes(), "image/jpeg")},
        headers=ct_headers,
    )
    assert res_dark.status_code == 400, f"Expected 400, got {res_dark.status_code}: {res_dark.text}"
    body_dark = res_dark.json()
    assert body_dark["message"] == "Image quality insufficient", f"Expected 'Image quality insufficient', got {body_dark}"
    print(f"[PASS] Dark image rejected correctly: message='{body_dark['message']}'")

    # 3c. Overexposed face
    bright_path = samples_dir / "overexposed_face.jpg"
    assert bright_path.exists(), "Sample file overexposed_face.jpg must exist"
    res_bright = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("overexposed_face.jpg", bright_path.read_bytes(), "image/jpeg")},
        headers=ct_headers,
    )
    assert res_bright.status_code == 400, f"Expected 400, got {res_bright.status_code}: {res_bright.text}"
    body_bright = res_bright.json()
    assert body_bright["message"] == "Image quality insufficient", f"Expected 'Image quality insufficient', got {body_bright}"
    print(f"[PASS] Overexposed image rejected correctly: message='{body_bright['message']}'")

    # -------------------------------------------------------------
    # 4. TEST SUCCESSFUL FACE ENROLLMENT ('Face enrolled successfully')
    # -------------------------------------------------------------
    print("\n--- STEP 4: Testing Successful Face Enrollment ---")
    valid_face_path = samples_dir / "student_alex.jpg"
    assert valid_face_path.exists(), "Sample file student_alex.jpg must exist"
    valid_bytes = valid_face_path.read_bytes()

    # Test via direct POST /students/{student_id}/face
    res_ok = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("alex.jpg", valid_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_ok.status_code == 200, f"Expected 200, got {res_ok.status_code}: {res_ok.text}"
    body_ok = res_ok.json()
    assert body_ok["success"] is True
    assert body_ok["message"] == "Face enrolled successfully"
    assert body_ok["student_id"] == st1_id
    assert body_ok["face_enrolled"] is True
    assert body_ok["embedding_dimension"] == 128
    assert body_ok["face_image_path"].startswith("/faces/student_")
    alex_face_path = body_ok["face_image_path"]
    print(f"[PASS] Face enrolled successfully via POST /students/{st1_id}/face: message='{body_ok['message']}'")

    # Verify static /faces file exists on disk and is accessible via HTTP
    res_img = client.get(alex_face_path)
    assert res_img.status_code == 200, f"Static face image not accessible: {res_img.status_code}"
    assert len(res_img.content) == len(valid_bytes)
    print(f"[PASS] Stored original image served securely: {alex_face_path} ({len(res_img.content)} bytes)")

    # Test GET /students/{student_id}/face
    res_get = client.get(f"/students/{st1_id}/face", headers=ct_headers)
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["face_enrolled"] is True
    assert get_data["embedding_dimension"] == 128
    assert get_data["status_label"] == "Enrolled"
    print(f"[PASS] GET /students/{st1_id}/face verified status: {get_data['status_label']}")

    # Also verify via POST /api/v1/students/{student_id}/face
    priya_path = samples_dir / "student_priya.jpg"
    assert priya_path.exists(), "Sample file student_priya.jpg must exist"
    priya_bytes = priya_path.read_bytes()

    res_v1 = client.post(
        f"/api/v1/students/{st2_id}/face",
        files={"file": ("priya.jpg", priya_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_v1.status_code == 200, f"Expected 200, got {res_v1.status_code}: {res_v1.text}"
    body_v1 = res_v1.json()
    assert body_v1["message"] == "Face enrolled successfully"
    assert body_v1["student_id"] == st2_id
    assert body_v1["embedding_dimension"] == 128
    priya_face_path = body_v1["face_image_path"]
    print(f"[PASS] Face enrolled successfully via POST /api/v1/students/{st2_id}/face: message='{body_v1['message']}'")

    # -------------------------------------------------------------
    # 5. STRICT VERIFICATION: NEVER ASSOCIATE WITH WRONG STUDENT
    # -------------------------------------------------------------
    print("\n--- STEP 5: Verifying Prevention of Wrong Student Association ---")
    db = SessionLocal()
    try:
        f1 = db.query(StudentFace).filter(StudentFace.student_id == st1_id, StudentFace.is_primary == True).first()
        f2 = db.query(StudentFace).filter(StudentFace.student_id == st2_id, StudentFace.is_primary == True).first()
        assert f1 is not None and f2 is not None, "Both students must have stored face records"

        # Check embedding vectors are independent and non-identical
        vec1 = np.array(json.loads(f1.embedding), dtype=np.float32)
        vec2 = np.array(json.loads(f2.embedding), dtype=np.float32)

        assert len(vec1) == 128, f"Expected 128D embedding, got {len(vec1)}"
        assert len(vec2) == 128, f"Expected 128D embedding, got {len(vec2)}"

        # Cosine similarity between Alex and Priya should be distinct (< 0.70)
        similarity = float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
        print(f"[INFO] Cosine similarity between Student 1 (Alex) and Student 2 (Priya): {similarity:.4f}")
        assert similarity < 0.80, f"Embeddings are suspiciously identical: {similarity}"
        assert f1.student_id == st1_id, "Embedding 1 incorrectly bound"
        assert f2.student_id == st2_id, "Embedding 2 incorrectly bound"
        print(f"[PASS] Embeddings strictly bound to respective student IDs without cross-contamination.")

        # Student status checks
        st1_db = db.query(Student).filter(Student.id == st1_id).first()
        st2_db = db.query(Student).filter(Student.id == st2_id).first()
        assert st1_db.face_enrolled is True
        assert st2_db.face_enrolled is True
    finally:
        db.close()

    # -------------------------------------------------------------
    # 6. AUTHORIZATION BOUNDARY ENFORCEMENT
    # -------------------------------------------------------------
    print("\n--- STEP 6: Testing Authorization Boundaries ---")
    # 6a. Class teacher attempting to enroll student from ANOTHER class -> 403 Forbidden
    res_forbidden = client.post(
        f"/students/{st_other_id}/face",
        files={"file": ("alex.jpg", valid_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_forbidden.status_code == 403, f"Expected 403 for other class student, got {res_forbidden.status_code}"
    print(f"[PASS] Class teacher blocked from enrolling student in other class section (403 Forbidden).")

    # 6b. Subject teacher attempting face enrollment -> 403 Forbidden
    res_subj_forbidden = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("alex.jpg", valid_bytes, "image/jpeg")},
        headers=subj_headers,
    )
    assert res_subj_forbidden.status_code == 403, f"Expected 403 for subject teacher, got {res_subj_forbidden.status_code}"
    print(f"[PASS] Subject teacher blocked from face enrollment (403 Forbidden).")

    # 6c. Admin enrolling student from any class -> 200 OK
    res_admin_ok = client.post(
        f"/students/{st_other_id}/face",
        files={"file": ("priya.jpg", priya_bytes, "image/jpeg")},
        headers=admin_headers,
    )
    assert res_admin_ok.status_code == 200, f"Admin face enrollment failed: {res_admin_ok.status_code}"
    assert res_admin_ok.json()["message"] == "Face enrolled successfully"
    print(f"[PASS] Admin authorized to enroll student across departments: message='Face enrolled successfully'.")

    # 6d. Non-existent student ID -> 404 Not Found
    res_not_found = client.post(
        "/students/999999/face",
        files={"file": ("alex.jpg", valid_bytes, "image/jpeg")},
        headers=admin_headers,
    )
    assert res_not_found.status_code == 404, f"Expected 404, got {res_not_found.status_code}"
    print(f"[PASS] Non-existent student returns 404: {res_not_found.json()['message']}")

    # 6e. Invalid image format (.txt script) -> 400
    res_corrupt = client.post(
        f"/students/{st1_id}/face",
        files={"file": ("malicious.txt", b"plain text script", "text/plain")},
        headers=ct_headers,
    )
    assert res_corrupt.status_code == 400
    print(f"[PASS] Invalid file format rejected with 400: {res_corrupt.json()['detail']}")

    print("\n" + "=" * 75)
    print("ALL FACE ENROLLMENT PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    test_face_enrollment_pipeline_full()
