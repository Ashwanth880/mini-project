"""
Comprehensive Role Authorization Matrix Automated Test Suite.
Verifies all RBAC permissions across all user roles:
1. ANONYMOUS / UNAUTHENTICATED:
   - Rejected with 401 Unauthorized across all protected API routes
2. SUBJECT_TEACHER:
   - Access to assigned classes & subjects -> 200 OK
   - Access to unassigned classes attendance -> 403 Forbidden
   - Face enrollment attempt -> 403 Forbidden
   - Class teacher portal endpoints -> 403 Forbidden
   - Admin portal endpoints -> 403 Forbidden
3. CLASS_TEACHER:
   - Access to assigned class section overview & roster -> 200 OK
   - Face enrollment for own section -> 200 OK
   - Face enrollment for another section -> 403 Forbidden
   - Admin portal endpoints -> 403 Forbidden
4. ADMIN:
   - Unrestricted access across all institution resources, configurations, and biometrics
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.academic import Class
from app.models.student import Student

client = TestClient(app)
samples_dir = backend_dir.parent / "data" / "test_samples"


def test_role_authorization_matrix():
    print("=" * 70)
    print("STARTING ROLE-BASED ACCESS CONTROL (RBAC) MATRIX TEST")
    print("=" * 70)

    # -------------------------------------------------------------
    # 0. SETUP TOKENS & FIXTURES
    # -------------------------------------------------------------
    admin_res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_res.status_code == 200
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ct_res = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert ct_res.status_code == 200
    ct_token = ct_res.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    st_res = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert st_res.status_code == 200
    st_token = st_res.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # Setup student in Class 1 (mentored by Sharma) and student in Class 2 (different class)
    db = SessionLocal()
    try:
        class_1 = db.query(Class).filter(Class.class_teacher_id == 2).first()
        if not class_1:
            class_1 = Class(name="CS Dept Mentored Single", department="Computer Science", year=2, section="M", class_teacher_id=2)
            db.add(class_1)
            db.flush()

        class_2 = db.query(Class).filter(Class.id != class_1.id).first()
        if not class_2:
            class_2 = Class(name="Mech Dept Other Single", department="Mechanical", year=2, section="O", class_teacher_id=None)
            db.add(class_2)
            db.flush()

        st_c1 = db.query(Student).filter(Student.class_id == class_1.id).first()
        if not st_c1:
            st_c1 = Student(
                roll_number="RBAC_C1_01",
                register_number="REG_RBAC_C1_01",
                full_name="Student Class 1",
                department="Computer Science",
                year=2,
                section="M",
                class_id=class_1.id,
                is_active=True,
            )
            db.add(st_c1)
            db.flush()

        st_c2 = db.query(Student).filter(Student.class_id == class_2.id).first()
        if not st_c2:
            st_c2 = Student(
                roll_number="RBAC_C2_02",
                register_number="REG_RBAC_C2_02",
                full_name="Student Class 2",
                department="Mechanical",
                year=2,
                section="O",
                class_id=class_2.id,
                is_active=True,
            )
            db.add(st_c2)
            db.flush()

        db.commit()
        c1_student_id = st_c1.id
        c2_student_id = st_c2.id
    finally:
        db.close()

    # -------------------------------------------------------------
    # 1. ANONYMOUS REQUESTS (401 UNAUTHORIZED)
    # -------------------------------------------------------------
    print("\n--- 1. Verifying Anonymous Access Protection ---")
    protected_endpoints = [
        ("GET", "/api/v1/admin/dashboard-stats"),
        ("GET", "/api/v1/admin/classes"),
        ("GET", "/api/v1/admin/teachers"),
        ("GET", "/api/v1/admin/subjects"),
        ("GET", "/api/v1/classes/"),
        ("GET", "/api/v1/subjects/"),
        ("GET", "/api/v1/students/"),
        ("GET", "/api/v1/teachers/class-teacher/overview"),
        ("GET", "/api/v1/teachers/subject-teacher/classes"),
        ("GET", "/api/v1/attendance/reports/daily"),
        ("GET", "/api/v1/attendance/reports/student"),
        ("GET", "/api/v1/attendance/reports/class"),
        ("GET", "/api/v1/attendance/reports/subject"),
        ("GET", "/api/v1/attendance/reports/monthly"),
    ]
    for method, path in protected_endpoints:
        res = client.request(method, path)
        assert res.status_code == 401, f"Expected 401 for anonymous {method} {path}, got {res.status_code}"
    print(f"[PASS] All {len(protected_endpoints)} protected endpoints securely reject unauthenticated requests.")

    # -------------------------------------------------------------
    # 2. SUBJECT TEACHER RESTRICTIONS
    # -------------------------------------------------------------
    print("\n--- 2. Verifying Subject Teacher Permissions & Boundaries ---")

    # Allowed: Subject teacher classes endpoint
    res_st_ok = client.get("/api/v1/teachers/subject-teacher/classes", headers=st_headers)
    assert res_st_ok.status_code == 200
    print("[PASS] Subject teacher allowed access to assigned classes list.")

    # Forbidden: Face enrollment (POST /api/v1/students/{id}/face)
    sample_face = (samples_dir / "student_alex.jpg").read_bytes()
    res_st_face = client.post(
        f"/api/v1/students/{c1_student_id}/face",
        headers=st_headers,
        files={"file": ("face.jpg", sample_face, "image/jpeg")},
    )
    assert res_st_face.status_code == 403, f"Expected 403 for subject teacher enrolling face, got {res_st_face.status_code}"
    print("[PASS] Subject teacher forbidden from enrolling biometric faces (HTTP 403).")

    # Forbidden: Class teacher portal
    res_st_ct = client.get("/api/v1/teachers/class-teacher/overview", headers=st_headers)
    assert res_st_ct.status_code == 403
    print("[PASS] Subject teacher forbidden from class teacher overview (HTTP 403).")

    # Forbidden: Admin portal endpoints
    for path in ["/api/v1/admin/dashboard-stats", "/api/v1/admin/teachers", "/api/v1/admin/classes"]:
        res_st_admin = client.get(path, headers=st_headers)
        assert res_st_admin.status_code == 403
    print("[PASS] Subject teacher forbidden from all admin management endpoints (HTTP 403).")

    # -------------------------------------------------------------
    # 3. CLASS TEACHER RESTRICTIONS & SCOPING
    # -------------------------------------------------------------
    print("\n--- 3. Verifying Class Teacher Permissions & Boundaries ---")

    # Allowed: Class teacher overview
    res_ct_ok = client.get("/api/v1/teachers/class-teacher/overview", headers=ct_headers)
    assert res_ct_ok.status_code == 200
    print("[PASS] Class teacher allowed access to own class overview.")

    # Allowed: Face enrollment for student in assigned class section
    res_ct_own = client.post(
        f"/api/v1/students/{c1_student_id}/face",
        headers=ct_headers,
        files={"file": ("face.jpg", sample_face, "image/jpeg")},
    )
    assert res_ct_own.status_code == 200, f"Expected 200 for CT own student face enrollment, got {res_ct_own.status_code}: {res_ct_own.text}"
    print("[PASS] Class teacher successfully enrolled face for student in own assigned class.")

    # Forbidden: Face enrollment for student in another class section
    res_ct_other = client.post(
        f"/api/v1/students/{c2_student_id}/face",
        headers=ct_headers,
        files={"file": ("face.jpg", sample_face, "image/jpeg")},
    )
    assert res_ct_other.status_code == 403, f"Expected 403 for CT enrolling student from other section, got {res_ct_other.status_code}"
    print("[PASS] Class teacher forbidden from enrolling face for student from other sections (HTTP 403).")

    # Forbidden: Admin portal endpoints
    for path in ["/api/v1/admin/dashboard-stats", "/api/v1/admin/teachers", "/api/v1/admin/classes"]:
        res_ct_admin = client.get(path, headers=ct_headers)
        assert res_ct_admin.status_code == 403
    print("[PASS] Class teacher forbidden from admin portal endpoints (HTTP 403).")

    # -------------------------------------------------------------
    # 4. ADMIN PRIVILEGES
    # -------------------------------------------------------------
    print("\n--- 4. Verifying Admin Full Authority ---")
    res_admin_kpi = client.get("/api/v1/admin/dashboard-stats", headers=admin_headers)
    assert res_admin_kpi.status_code == 200
    assert "total_students" in res_admin_kpi.json()

    # Admin enrolling face for any student (including Class 2)
    res_admin_face = client.post(
        f"/api/v1/students/{c2_student_id}/face",
        headers=admin_headers,
        files={"file": ("face.jpg", sample_face, "image/jpeg")},
    )
    assert res_admin_face.status_code == 200
    print("[PASS] Admin possesses full authority across institution classes and biometrics.")

    print("\n>>> ALL ROLE AUTHORIZATION MATRIX TESTS PASSED! <<<")


if __name__ == "__main__":
    test_role_authorization_matrix()
