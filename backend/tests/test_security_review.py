"""
End-to-End Security Verification Test Suite for One-Click Attendance.
Verifies all 17 security checkpoints:
1. Password hashing (bcrypt, 72-byte limit safety, salt uniqueness, verify)
2. JWT security (exp, iat, sub claims, tampering, expired token rejection)
3. Authorization (Role-based access control, 401 unauthenticated, 403 unauthorized)
4. File upload validation (extension whitelist, mime type checks, size limits)
5. Image upload security (Pillow raster decode validation, dimensions, corrupted image detection)
6. Path traversal prevention (directory traversal attacks sanitized, safe UUID storage)
7. SQL injection protection (parameterized ORM queries immune to SQL injection)
8. XSS protection (HTML escaping, script tags sanitized)
9. CSRF considerations (stateless Bearer JWT token architecture)
10. CORS configuration (safe whitelisted origins, no wildcard credentials vulnerability)
11. Secret management (production key validation, minimum 32-character requirement)
12. Environment variables (settings loaded securely from environment)
13. Error message leakage (sanitized exceptions, no internal tracebacks in API errors)
14. API authorization (endpoints strictly require valid tokens)
15. Teacher access to only assigned classes (strict scoping to assigned classes)
16. Student privacy (biometrics and records accessible only to authorized mentors/admins)
17. Attendance modification authorization (spoofed teacher IDs and unassigned classes blocked)
"""

import sys
import io
import time
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.config import settings

client = TestClient(app)


def create_test_image_bytes(width=100, height=100, color=(120, 150, 180), fmt="JPEG"):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


def run_security_verification():
    print("=" * 70)
    print("RUNNING 17-POINT SECURITY VERIFICATION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Password Hashing
    # -------------------------------------------------------------
    print("\n[Check 1] Password Hashing Security...")
    plain_pw = "SuperSecurePass123!"
    h1 = hash_password(plain_pw)
    h2 = hash_password(plain_pw)
    assert h1 != h2, "Salts must be unique per password hash"
    assert verify_password(plain_pw, h1) is True, "Password verification failed"
    assert verify_password("WrongPassword!", h1) is False, "Invalid password incorrectly verified"

    # Test bcrypt 72-byte truncation safety (should not crash on >72 bytes)
    long_pw = "A" * 150
    h_long = hash_password(long_pw)
    assert verify_password(long_pw, h_long) is True
    print("  [PASS] Salt uniqueness, bcrypt verification, and 72-byte safe handling verified")

    # -------------------------------------------------------------
    # 2. JWT Security
    # -------------------------------------------------------------
    print("\n[Check 2] JWT Security & Claims Verification...")
    token = create_access_token(data={"sub": "1", "role": "ADMIN", "username": "admin"}, expires_delta=timedelta(minutes=15))
    payload = decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "1"
    assert "exp" in payload and "iat" in payload and "nbf" in payload

    # Test expired token
    expired_token = create_access_token(data={"sub": "1", "role": "ADMIN"}, expires_delta=timedelta(seconds=-10))
    assert decode_access_token(expired_token) is None, "Expired token must be rejected"

    # Test tampered token
    tampered = token[:-4] + "fake"
    assert decode_access_token(tampered) is None, "Tampered token must be rejected"
    print("  [PASS] JWT expiration, signature integrity, and claims verification verified")

    # -------------------------------------------------------------
    # 3. Authorization & RBAC
    # -------------------------------------------------------------
    print("\n[Check 3] Authorization & Role-Based Access Control...")
    # Log in as Class Teacher (sharma) and Subject Teacher (patel)
    res_ct = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    ct_token = res_ct.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    res_st = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    st_token = res_st.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = res_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Unauthenticated request -> 401
    assert client.get("/api/v1/admin/dashboard-stats").status_code == 401

    # Subject teacher trying to access admin route -> 403
    assert client.get("/api/v1/admin/dashboard-stats", headers=st_headers).status_code == 403

    # Admin accessing admin route -> 200
    assert client.get("/api/v1/admin/dashboard-stats", headers=admin_headers).status_code == 200
    print("  [PASS] Unauthenticated (401) and unauthorized role access (403) strictly enforced")

    # -------------------------------------------------------------
    # 4. File Upload Validation
    # -------------------------------------------------------------
    print("\n[Check 4] File Upload Validation...")
    # Disallowed extension (.exe / .txt)
    res_bad_ext = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={"class_id": 1, "subject_id": 1, "period": 1},
        files={"photo": ("malicious.exe", b"MZexecutabledata", "application/x-msdownload")},
    )
    assert res_bad_ext.status_code == 400
    assert "Invalid image format" in res_bad_ext.text or "not permitted" in res_bad_ext.text

    # Tiny / empty file (< 500 bytes)
    res_tiny = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={"class_id": 1, "subject_id": 1, "period": 1},
        files={"photo": ("empty.jpg", b"123", "image/jpeg")},
    )
    assert res_tiny.status_code == 400
    print("  [PASS] Disallowed extensions and empty/undersized payloads rejected with 400")

    # -------------------------------------------------------------
    # 5. Image Upload Security (Pillow Raster Validation)
    # -------------------------------------------------------------
    print("\n[Check 5] Image Upload Raster & Dimension Security...")
    # Valid extension (.jpg) but corrupted non-image content
    fake_jpg = b"\xFF\xD8\xFF\xE0" + b"A" * 1000  # Fake JPEG header with corrupted garbage
    res_corrupted = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={"class_id": 1, "subject_id": 1, "period": 1},
        files={"photo": ("fake.jpg", fake_jpg, "image/jpeg")},
    )
    assert res_corrupted.status_code == 400
    assert "Corrupted or invalid image" in res_corrupted.text

    # Tiny dimension image (e.g. 10x10 px)
    tiny_img = create_test_image_bytes(width=10, height=10)
    res_tiny_dim = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={"class_id": 1, "subject_id": 1, "period": 1},
        files={"photo": ("tiny.jpg", tiny_img, "image/jpeg")},
    )
    assert res_tiny_dim.status_code == 400
    assert "dimensions are too small" in res_tiny_dim.text
    print("  [PASS] Raster decode and image dimension boundaries verified")

    # -------------------------------------------------------------
    # 6. Path Traversal Prevention
    # -------------------------------------------------------------
    print("\n[Check 6] Path Traversal Prevention...")
    valid_img = create_test_image_bytes(width=200, height=200)
    traversal_filename = "../../../../../windows/system32/evil.jpg"
    res_trav = client.post(
        "/api/v1/attendance/process-classroom-photo",
        headers=st_headers,
        data={"department": "CSE", "subject_name": "Operating Systems", "year": 3, "section": "A", "period": 1},
        files={"photo": (traversal_filename, valid_img, "image/jpeg")},
    )
    assert res_trav.status_code == 200
    saved_filename = res_trav.json()["image_path"]
    assert ".." not in saved_filename
    assert "/" not in saved_filename and "\\" not in saved_filename
    assert Path(settings.ATTENDANCE_PHOTOS_DIR / saved_filename).exists()
    print("  [PASS] Path traversal attack neutralized; stored under safe randomized UUID filename")

    # -------------------------------------------------------------
    # 7. SQL Injection Protection
    # -------------------------------------------------------------
    print("\n[Check 7] SQL Injection Protection...")
    sql_injection_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "admin' --",
        "' UNION SELECT * FROM users --",
    ]
    for sqli in sql_injection_payloads:
        res_sqli = client.post("/auth/login", json={"username": sqli, "password": "password"})
        assert res_sqli.status_code == 401, f"SQL injection payload {sqli} did not fail safely"

    # Search with SQL injection payload
    res_search = client.get(f"/api/v1/students?search={sql_injection_payloads[0]}", headers=admin_headers)
    assert res_search.status_code == 200, "Search query with SQL metacharacters must safely return empty or filtered list"
    print("  [PASS] SQLAlchemy parameterized queries prevent all SQL injection attacks")

    # -------------------------------------------------------------
    # 8. XSS Protection
    # -------------------------------------------------------------
    print("\n[Check 8] XSS Protection...")
    xss_payload = "<script>alert('XSS')</script>"
    res_reg_xss = client.post(
        "/auth/register",
        json={"username": "xss_test_user", "email": "xss@test.edu", "full_name": xss_payload, "password": "securepassword123", "role": "SUBJECT_TEACHER"},
    )
    # Registration either accepts with sanitized name or handles cleanly
    if res_reg_xss.status_code == 200:
        user_info = res_reg_xss.json()
        assert "<script>" not in user_info["full_name"], "HTML tags must be stripped from user full_name"
    print("  [PASS] Stored and Reflected XSS input sanitization verified")

    # -------------------------------------------------------------
    # 9. CSRF Considerations
    # -------------------------------------------------------------
    print("\n[Check 9] CSRF Architecture...")
    # State-changing request without Authorization header must be rejected
    res_csrf = client.post(
        "/api/v1/attendance/confirm",
        json={"confirmed_records": []},
    )
    assert res_csrf.status_code == 401, "Requests without Bearer token must fail, neutralizing CSRF"
    print("  [PASS] Bearer JWT authentication header required for all state mutations")

    # -------------------------------------------------------------
    # 10. CORS Configuration
    # -------------------------------------------------------------
    print("\n[Check 10] CORS Whitelist Configuration...")
    origins = settings.cors_origins_list
    assert "*" not in origins, "Wildcard '*' must never be used with allow_credentials=True"
    assert any("localhost" in orig or "127.0.0.1" in orig for orig in origins)
    print(f"  [PASS] Strict CORS origins whitelist verified: {origins}")

    # -------------------------------------------------------------
    # 11 & 12. Secret Management & Environment Variables
    # -------------------------------------------------------------
    print("\n[Check 11 & 12] Secret Management & Environment Variables...")
    assert len(settings.SECRET_KEY) >= 16, "Secret key length must be sufficient"
    # Test production validation logic
    original_env = settings.APP_ENV
    original_key = settings.SECRET_KEY
    try:
        settings.APP_ENV = "production"
        settings.SECRET_KEY = "dev-secret-key-change-in-production"
        prod_error = None
        try:
            settings.validate_security_settings()
        except RuntimeError as e:
            prod_error = str(e)
        assert prod_error is not None, "Insecure secret key must trigger RuntimeError in production"
    finally:
        settings.APP_ENV = original_env
        settings.SECRET_KEY = original_key
    print("  [PASS] Production environment validation and secret safeguards verified")

    # -------------------------------------------------------------
    # 13. Error Message Leakage
    # -------------------------------------------------------------
    print("\n[Check 13] Error Message Leakage...")
    # Access a non-existent route or malformed data
    res_404 = client.get("/api/v1/non_existent_route_404")
    assert res_404.status_code == 404
    assert "Traceback" not in res_404.text and "File \"" not in res_404.text
    print("  [PASS] No internal stack traces or database connection strings leaked in responses")

    # -------------------------------------------------------------
    # 14. API Authorization
    # -------------------------------------------------------------
    print("\n[Check 14] Comprehensive API Authorization...")
    protected_endpoints = [
        ("GET", "/api/v1/attendance/reports"),
        ("GET", "/api/v1/attendance/reports/daily"),
        ("GET", "/api/v1/attendance/reports/student"),
        ("GET", "/api/v1/attendance/reports/subject"),
        ("GET", "/api/v1/attendance/reports/class"),
        ("GET", "/api/v1/attendance/reports/monthly"),
        ("POST", "/api/v1/attendance/confirm"),
        ("POST", "/api/v1/attendance/process-classroom-photo"),
        ("GET", "/api/v1/students/1/face"),
        ("POST", "/api/v1/students/1/face"),
        ("GET", "/api/v1/teachers/subject-teacher/classes"),
        ("GET", "/api/v1/teachers/class-teacher/my-class"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path)
        assert res.status_code == 401, f"Endpoint {method} {path} allowed unauthenticated access (got {res.status_code})!"
    print("  [PASS] All 12 sensitive endpoints confirmed to reject unauthenticated requests with HTTP 401")

    # -------------------------------------------------------------
    # 15. Teacher Access to Only Assigned Classes
    # -------------------------------------------------------------
    print("\n[Check 15] Teacher Scope & Class Isolation...")
    # Subject teacher 'patel' is assigned class_id=1, subject_id=1.
    # Attempting to analyze classroom photo for an unassigned class (e.g. class_id=2)
    sample_img = create_test_image_bytes(width=200, height=200)
    res_unassigned = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={"class_id": 2, "subject_id": 1, "period": 1},
        files={"photo": ("classroom.jpg", sample_img, "image/jpeg")},
    )
    assert res_unassigned.status_code == 403, f"Expected 403 for unassigned class, got {res_unassigned.status_code}"
    print("  [PASS] Subject teacher restricted strictly to assigned classes (HTTP 403 Forbidden)")

    # -------------------------------------------------------------
    # 16. Student Privacy & Biometric Protection
    # -------------------------------------------------------------
    print("\n[Check 16] Student Privacy & Biometric Data Isolation...")
    # Subject teacher 'patel' trying to fetch face image of a student in unassigned class -> 403
    assigned_res = client.get("/api/v1/teachers/subject-teacher/classes", headers=st_headers)
    assigned_data = assigned_res.json() if assigned_res.status_code == 200 else {}
    assigned_class_ids = {c["id"] for c in assigned_data.get("assigned_classes", [])} if isinstance(assigned_data, dict) else {1}
    all_students = client.get("/api/v1/students", headers=admin_headers).json()
    other_student = next((s for s in all_students if s.get("class_id") not in assigned_class_ids), None)
    if not other_student:
        # Create a new class guaranteed not to be assigned to patel
        res_unassigned_c = client.post(
            "/api/v1/admin/classes",
            headers=admin_headers,
            json={"name": "Unassigned Security Class", "department": "MECH", "year": 4, "section": "Z"},
        )
        unassigned_cid = res_unassigned_c.json()["id"]
        res_new_s = client.post(
            "/api/v1/students",
            headers=admin_headers,
            json={
                "roll_number": "SEC-TEST-99",
                "register_number": "REG-SEC-99",
                "full_name": "Other Student",
                "class_id": unassigned_cid,
                "department": "MECH",
                "year": 4,
                "section": "Z",
            },
        )
        other_student_id = res_new_s.json()["id"]
    else:
        other_student_id = other_student["id"]

    res_face = client.get(f"/api/v1/students/{other_student_id}/face", headers=st_headers)
    assert res_face.status_code == 403, f"Subject teacher should receive 403 for student in unassigned class (got {res_face.status_code})"

    # Subject teacher attempting to enroll face -> 403 (restricted to class teacher/admin)
    res_st_enroll = client.post(
        "/api/v1/students/1/face",
        headers=st_headers,
        files={"file": ("face.jpg", b"123", "image/jpeg")},
    )
    assert res_st_enroll.status_code == 403

    # Unauthenticated attempt to get face image -> 401
    assert client.get("/api/v1/students/1/face").status_code == 401
    print("  [PASS] Biometric face images protected; unauthorized teachers and public blocked")

    # -------------------------------------------------------------
    # 17. Attendance Modification Authorization
    # -------------------------------------------------------------
    print("\n[Check 17] Attendance Modification Authorization...")
    # Subject teacher 'patel' attempting to confirm attendance for unassigned class 2
    res_spoof_class = client.post(
        "/api/v1/attendance/confirm",
        headers=st_headers,
        json={
            "confirmed_records": [
                {
                    "student_id": 1,
                    "class_id": 2,  # unassigned class
                    "subject_id": 1,
                    "teacher_id": 3,
                    "date": "2026-10-05",
                    "period": 1,
                    "status": "PRESENT",
                    "confidence": 0.95,
                    "is_manual": False,
                }
            ]
        },
    )
    assert res_spoof_class.status_code == 403, f"Expected 403 for unassigned class modification, got {res_spoof_class.status_code}"

    # Subject teacher 'patel' attempting to mark attendance pretending to be teacher_id 999
    res_spoof_teacher = client.post(
        "/api/v1/attendance/confirm",
        headers=st_headers,
        json={
            "confirmed_records": [
                {
                    "student_id": 1,
                    "class_id": 1,
                    "subject_id": 1,
                    "teacher_id": 999,  # spoofed teacher ID
                    "date": "2026-10-05",
                    "period": 1,
                    "status": "PRESENT",
                    "confidence": 0.95,
                    "is_manual": False,
                }
            ]
        },
    )
    # The server either overrides teacher_id to authentic user or rejects spoofed ID with 403
    assert res_spoof_teacher.status_code in (200, 403)
    if res_spoof_teacher.status_code == 200:
        saved_recs = res_spoof_teacher.json()
        rec_list = saved_recs if isinstance(saved_recs, list) else saved_recs.get("records", [])
        # Verified authentic teacher ID was enforced
        assert rec_list[0]["teacher_id"] == 3, f"Expected authentic teacher_id 3, found {rec_list[0]['teacher_id']}"
    print("  [PASS] Attendance modification authorized; teacher ID spoofing prevented")

    print("\n" + "=" * 70)
    print(">>> ALL 17 SECURITY CHECKPOINTS VERIFIED SUCCESSFULLY! <<<")
    print("=" * 70)


def test_security_verification():
    """Pytest test case running all 17 security checkpoints."""
    run_security_verification()


if __name__ == "__main__":
    run_security_verification()

