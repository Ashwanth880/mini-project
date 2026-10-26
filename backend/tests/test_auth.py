"""
Authentication & Role-Based Authorization Automated Tests.
Covers:
1. Valid login (ADMIN, CLASS_TEACHER, SUBJECT_TEACHER)
2. Invalid password
3. Invalid user
4. Role-based access control (403 Forbidden for insufficient role, 401 for unauthenticated)
5. User registration & verification
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_auth_and_roles():
    print("=== 1. TEST VALID LOGIN ===")
    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.text}"
    admin_data = res_admin.json()
    admin_token = admin_data["access_token"]
    assert admin_data["user"]["role"] == "ADMIN"
    print(f"[PASS] Admin login succeeded, role: {admin_data['user']['role']}")

    res_class_teacher = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert res_class_teacher.status_code == 200, f"Class teacher login failed: {res_class_teacher.text}"
    ct_data = res_class_teacher.json()
    ct_token = ct_data["access_token"]
    assert ct_data["user"]["role"] == "CLASS_TEACHER"
    print(f"[PASS] Class Teacher login succeeded, role: {ct_data['user']['role']}")

    res_subj_teacher = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert res_subj_teacher.status_code == 200, f"Subject teacher login failed: {res_subj_teacher.text}"
    st_data = res_subj_teacher.json()
    st_token = st_data["access_token"]
    assert st_data["user"]["role"] == "SUBJECT_TEACHER"
    print(f"[PASS] Subject Teacher login succeeded, role: {st_data['user']['role']}")

    print("\n=== 2. TEST INVALID PASSWORD ===")
    res_inv_pwd = client.post("/auth/login", json={"username": "admin", "password": "wrongpassword!"})
    assert res_inv_pwd.status_code == 401, f"Expected 401 for wrong password, got {res_inv_pwd.status_code}"
    print(f"[PASS] Invalid password rejected with HTTP 401: {res_inv_pwd.json()['detail']}")

    print("\n=== 3. TEST INVALID USER ===")
    res_inv_user = client.post("/auth/login", json={"username": "nonexistent_user", "password": "somepassword"})
    assert res_inv_user.status_code == 401, f"Expected 401 for nonexistent user, got {res_inv_user.status_code}"
    print(f"[PASS] Invalid user rejected with HTTP 401: {res_inv_user.json()['detail']}")

    print("\n=== 4. TEST ROLE-BASED ACCESS & PROTECTED ROUTES ===")
    # Unauthenticated request to admin endpoint -> 401
    res_no_auth = client.get("/api/v1/admin/dashboard-stats")
    assert res_no_auth.status_code == 401, f"Expected 401 for unauthenticated request, got {res_no_auth.status_code}"
    print("[PASS] Unauthenticated request to /admin/dashboard-stats returned HTTP 401")

    # SUBJECT_TEACHER attempting to access ADMIN endpoint -> 403 Forbidden
    res_forbidden = client.get("/api/v1/admin/dashboard-stats", headers={"Authorization": f"Bearer {st_token}"})
    assert res_forbidden.status_code == 403, f"Expected 403 for subject teacher, got {res_forbidden.status_code}"
    print(f"[PASS] SUBJECT_TEACHER access to /admin/dashboard-stats denied with HTTP 403: {res_forbidden.json()['detail']}")

    # CLASS_TEACHER attempting to access ADMIN endpoint -> 403 Forbidden
    res_ct_forbidden = client.get("/api/v1/admin/dashboard-stats", headers={"Authorization": f"Bearer {ct_token}"})
    assert res_ct_forbidden.status_code == 403, f"Expected 403 for class teacher, got {res_ct_forbidden.status_code}"
    print(f"[PASS] CLASS_TEACHER access to /admin/dashboard-stats denied with HTTP 403: {res_ct_forbidden.json()['detail']}")

    # ADMIN accessing ADMIN endpoint -> 200 OK
    res_admin_access = client.get("/api/v1/admin/dashboard-stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin_access.status_code == 200, f"Expected 200 for admin, got {res_admin_access.status_code}"
    print(f"[PASS] ADMIN access to /admin/dashboard-stats allowed with HTTP 200 (Admin: {res_admin_access.json()['admin_user']})")

    # SUBJECT_TEACHER attempting to access CLASS_TEACHER overview -> 403 Forbidden
    res_st_to_ct = client.get("/api/v1/teachers/class-teacher/overview", headers={"Authorization": f"Bearer {st_token}"})
    assert res_st_to_ct.status_code == 403, f"Expected 403 for subject teacher accessing class teacher, got {res_st_to_ct.status_code}"
    print("[PASS] SUBJECT_TEACHER access to /teachers/class-teacher/overview denied with HTTP 403")

    # CLASS_TEACHER accessing CLASS_TEACHER overview -> 200 OK
    res_ct_access = client.get("/api/v1/teachers/class-teacher/overview", headers={"Authorization": f"Bearer {ct_token}"})
    assert res_ct_access.status_code == 200, f"Expected 200 for class teacher, got {res_ct_access.status_code}"
    print(f"[PASS] CLASS_TEACHER access to /teachers/class-teacher/overview allowed with HTTP 200 (Teacher: {res_ct_access.json()['teacher_name']})")

    # SUBJECT_TEACHER accessing SUBJECT_TEACHER endpoint -> 200 OK
    res_st_access = client.get("/api/v1/teachers/subject-teacher/classes", headers={"Authorization": f"Bearer {st_token}"})
    assert res_st_access.status_code == 200, f"Expected 200 for subject teacher, got {res_st_access.status_code}"
    print(f"[PASS] SUBJECT_TEACHER access to /teachers/subject-teacher/classes allowed with HTTP 200 (Teacher: {res_st_access.json()['teacher_name']})")

    # Test GET /auth/me for all 3 tokens
    for tok, expected_user in [(admin_token, "admin"), (ct_token, "sharma"), (st_token, "patel")]:
        res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert res_me.status_code == 200
        assert res_me.json()["username"] == expected_user
    print("[PASS] GET /auth/me verified for all roles!")

    print("\n=== 5. TEST USER REGISTRATION ===")
    new_user_payload = {
        "username": "new_lecturer_demo",
        "email": "demo_lecturer@college.edu",
        "full_name": "Prof. Demo Lecturer",
        "password": "lecturepass123",
        "role": "SUBJECT_TEACHER",
        "department": "Electronics",
    }
    # Check if already registered in a previous run, or register
    res_reg = client.post("/auth/register", json=new_user_payload)
    if res_reg.status_code == 201:
        print(f"[PASS] User registered successfully: {res_reg.json()['username']} (role: {res_reg.json()['role']})")
    elif res_reg.status_code == 400:
        print("[PASS] Registration validation works: user already exists")

    # Test logging in with newly registered user
    res_new_login = client.post("/auth/login", json={"username": "new_lecturer_demo", "password": "lecturepass123"})
    assert res_new_login.status_code == 200
    print("[PASS] Registered user logged in successfully with JWT token!")

    print("\n>>> ALL AUTHENTICATION & ROLE-BASED AUTHORIZATION TESTS PASSED! <<<")


if __name__ == "__main__":
    test_auth_and_roles()
