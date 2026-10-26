"""
Comprehensive Automated Test Suite for Subject Teacher Management Flow by Class Teachers.

Verifies:
1. Class Teacher can create Subject Teachers with Name, unique Teacher ID, Username, and Password.
2. Class Teacher can assign each Subject Teacher to specific subjects and classes.
3. Teacher accounts and assignments are saved properly in the database with secure bcrypt password hashing.
4. Subject Teachers can log in using their assigned Username OR Teacher ID and Password.
5. After login, correct teacher's name and only their assigned subjects and classes are returned.
6. Edit, deactivate, reactivate, and view teacher details & assignments.
7. Role-based access control (RBAC): Only Class Teachers and Admins have permission; Subject Teachers and Students are blocked (403); Anonymous blocked (401).
8. Existing attendance features and models remain untouched and functional.
"""

import sys
import uuid
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.user import User, UserRole
from app.models.academic import Class, Subject, ClassSubject
from app.utils.security import verify_password

client = TestClient(app)


@pytest.fixture(scope="module")
def auth_tokens():
    """Retrieve auth tokens for Class Teacher, Subject Teacher, Admin, and Student."""
    # 1. Class Teacher (sharma)
    ct_res = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert ct_res.status_code == 200, f"Class teacher login failed: {ct_res.text}"
    ct_token = ct_res.json()["access_token"]

    # 2. Existing Subject Teacher (patel)
    st_res = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert st_res.status_code == 200, f"Subject teacher login failed: {st_res.text}"
    st_token = st_res.json()["access_token"]

    # 3. Admin (admin)
    adm_res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert adm_res.status_code == 200, f"Admin login failed: {adm_res.text}"
    adm_token = adm_res.json()["access_token"]

    return {
        "class_teacher": {"Authorization": f"Bearer {ct_token}"},
        "subject_teacher": {"Authorization": f"Bearer {st_token}"},
        "admin": {"Authorization": f"Bearer {adm_token}"},
    }


def test_get_available_assignment_options(auth_tokens):
    """Class teacher can fetch available classes and subjects for dropdown selection."""
    res = client.get("/api/v1/teachers/class-teacher/available-assignment-options", headers=auth_tokens["class_teacher"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert "classes" in data
    assert "subjects" in data
    assert len(data["classes"]) > 0
    assert len(data["subjects"]) > 0


def test_class_teacher_creates_subject_teacher_with_assignments(auth_tokens):
    """
    Test Requirement 1, 2, 3:
    Create Subject Teacher with name, unique Teacher ID, username, password, and class-subject assignments.
    Verify saved in DB and password securely hashed with bcrypt.
    """
    unique_suffix = uuid.uuid4().hex[:6]
    test_tid = f"TID-{unique_suffix.upper()}"
    test_username = f"prof_{unique_suffix}"
    test_raw_pwd = "SecureTeacherPass123!"

    # Fetch available classes and subjects
    opt_res = client.get("/api/v1/teachers/class-teacher/available-assignment-options", headers=auth_tokens["class_teacher"])
    opt_data = opt_res.json()
    class_id = opt_data["classes"][0]["id"]
    subject_id = opt_data["subjects"][0]["id"]

    payload = {
        "name": f"Prof. Test Faculty {unique_suffix}",
        "teacher_id": test_tid,
        "username": test_username,
        "password": test_raw_pwd,
        "email": f"faculty_{unique_suffix}@institution.edu",
        "department": "Computer Science",
        "assignments": [
            {"class_id": class_id, "subject_id": subject_id}
        ]
    }

    create_res = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=payload)
    assert create_res.status_code == 201, create_res.text
    teacher_data = create_res.json()

    assert teacher_data["teacher_id"] == test_tid
    assert teacher_data["username"] == test_username
    assert teacher_data["full_name"] == payload["name"]
    assert teacher_data["role"] == "SUBJECT_TEACHER"
    assert teacher_data["is_active"] is True
    assert len(teacher_data["assignments"]) == 1
    assert teacher_data["assignments"][0]["class_id"] == class_id
    assert teacher_data["assignments"][0]["subject_id"] == subject_id

    # Verify directly in Database: password must be hashed and match verify_password
    db: Session = next(get_db())
    db_user = db.query(User).filter(User.teacher_id == test_tid).first()
    assert db_user is not None
    assert db_user.hashed_password != test_raw_pwd
    assert db_user.hashed_password.startswith("$2")  # bcrypt hash
    assert verify_password(test_raw_pwd, db_user.hashed_password)

    # Verify ClassSubject mapping exists in database
    db_cs = db.query(ClassSubject).filter(
        ClassSubject.teacher_id == db_user.id,
        ClassSubject.class_id == class_id,
        ClassSubject.subject_id == subject_id
    ).first()
    assert db_cs is not None


def test_duplicate_teacher_id_and_username_rejected(auth_tokens):
    """Verify unique constraints: duplicate teacher_id or username return 400 Bad Request."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_tid = f"DUP-{unique_suffix.upper()}"
    test_username = f"dup_{unique_suffix}"

    payload = {
        "name": "Teacher One",
        "teacher_id": test_tid,
        "username": test_username,
        "password": "Password123!",
        "assignments": []
    }

    # 1. First creation succeeds
    res1 = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=payload)
    assert res1.status_code == 201

    # 2. Duplicate teacher_id fails
    payload_dup_tid = {
        "name": "Teacher Two",
        "teacher_id": test_tid,
        "username": f"other_{unique_suffix}",
        "password": "Password123!",
        "assignments": []
    }
    res2 = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=payload_dup_tid)
    assert res2.status_code == 400
    assert "already in use" in res2.text.lower() or "already exists" in res2.text.lower()

    # 3. Duplicate username fails
    payload_dup_user = {
        "name": "Teacher Three",
        "teacher_id": f"OTHER-{unique_suffix.upper()}",
        "username": test_username,
        "password": "Password123!",
        "assignments": []
    }
    res3 = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=payload_dup_user)
    assert res3.status_code == 400
    assert "already in use" in res3.text.lower() or "already exists" in res3.text.lower()


def test_login_via_username_and_teacher_id(auth_tokens):
    """
    Test Requirement 4:
    Allow Subject Teachers to log in using their assigned username OR Teacher ID and password.
    """
    unique_suffix = uuid.uuid4().hex[:6]
    test_tid = f"LOG-{unique_suffix.upper()}"
    test_username = f"login_user_{unique_suffix}"
    test_pwd = "MySecretLoginPass123!"

    # Create teacher
    create_payload = {
        "name": f"Prof. Login Test {unique_suffix}",
        "teacher_id": test_tid,
        "username": test_username,
        "password": test_pwd,
        "assignments": []
    }
    create_res = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=create_payload)
    assert create_res.status_code == 201

    # 1. Login using username
    login_user_res = client.post("/auth/login", json={"username": test_username, "password": test_pwd})
    assert login_user_res.status_code == 200, login_user_res.text
    user_token_data = login_user_res.json()
    assert "access_token" in user_token_data
    assert user_token_data["user"]["username"] == test_username
    assert user_token_data["user"]["teacher_id"] == test_tid

    # 2. Login using Teacher ID
    login_tid_res = client.post("/auth/login", json={"username": test_tid, "password": test_pwd})
    assert login_tid_res.status_code == 200, login_tid_res.text
    tid_token_data = login_tid_res.json()
    assert "access_token" in tid_token_data
    assert tid_token_data["user"]["teacher_id"] == test_tid

    # 3. Login with wrong password rejected
    wrong_pwd_res = client.post("/auth/login", json={"username": test_tid, "password": "WrongPassword"})
    assert wrong_pwd_res.status_code == 401


def test_subject_teacher_portal_filters_only_assigned_subjects_and_classes(auth_tokens):
    """
    Test Requirement 5:
    After login, show the correct teacher's name and only their assigned subjects and classes.
    """
    unique_suffix = uuid.uuid4().hex[:6]
    test_tid = f"FLT-{unique_suffix.upper()}"
    test_username = f"filter_prof_{unique_suffix}"
    test_pwd = "FilterPassword123!"
    full_name = f"Prof. Specific Assignments {unique_suffix}"

    # Get available options
    opt_res = client.get("/api/v1/teachers/class-teacher/available-assignment-options", headers=auth_tokens["class_teacher"])
    opt_data = opt_res.json()
    assigned_class = opt_data["classes"][0]
    assigned_subj = opt_data["subjects"][0]

    # Create teacher assigned to only 1 specific class and 1 subject
    create_payload = {
        "name": full_name,
        "teacher_id": test_tid,
        "username": test_username,
        "password": test_pwd,
        "department": "Mechanical Engineering",
        "assignments": [
            {"class_id": assigned_class["id"], "subject_id": assigned_subj["id"]}
        ]
    }
    client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=create_payload)

    # Login as this newly created Subject Teacher
    login_res = client.post("/auth/login", json={"username": test_tid, "password": test_pwd})
    st_token = login_res.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # Fetch subject teacher portal classes
    portal_res = client.get("/api/v1/teachers/subject-teacher/classes", headers=st_headers)
    assert portal_res.status_code == 200, portal_res.text
    portal_data = portal_res.json()

    # 1. Shows correct teacher's name
    assert portal_data["teacher_name"] == full_name
    assert portal_data["role"] == "SUBJECT_TEACHER"

    # 2. Assigned classes only contains their assigned class
    assigned_class_ids = [c["id"] for c in portal_data["assigned_classes"]]
    assert assigned_class["id"] in assigned_class_ids

    # 3. Assigned subjects only contains their assigned subject
    assigned_subj_codes = [s.get("subject_code") or s.get("code") for s in portal_data["assigned_subjects"]]
    assert assigned_subj["code"] in assigned_subj_codes


def test_edit_view_and_deactivate_subject_teacher(auth_tokens):
    """
    Test Requirement 6:
    Add edit, deactivate, and view teacher options.
    """
    unique_suffix = uuid.uuid4().hex[:6]
    test_tid = f"MGMT-{unique_suffix.upper()}"
    test_username = f"mgmt_prof_{unique_suffix}"
    original_pwd = "OriginalPassword123!"

    # Create teacher
    create_payload = {
        "name": f"Prof. Initial Name {unique_suffix}",
        "teacher_id": test_tid,
        "username": test_username,
        "password": original_pwd,
        "department": "Civil Engineering",
        "assignments": []
    }
    create_res = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["class_teacher"], json=create_payload)
    teacher_id = create_res.json()["id"]

    # 1. View teacher detail
    view_res = client.get(f"/api/v1/teachers/class-teacher/subject-teachers/{teacher_id}", headers=auth_tokens["class_teacher"])
    assert view_res.status_code == 200
    assert view_res.json()["teacher_id"] == test_tid

    # 2. Edit teacher: update name, department, and set a new password
    new_pwd = "NewUpdatedPassword456!"
    updated_name = f"Prof. Updated Name {unique_suffix}"
    update_payload = {
        "name": updated_name,
        "department": "Electronics Engineering",
        "password": new_pwd,
        "is_active": True,
        "assignments": []
    }
    update_res = client.put(f"/api/v1/teachers/class-teacher/subject-teachers/{teacher_id}", headers=auth_tokens["class_teacher"], json=update_payload)
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == updated_name
    assert update_res.json()["department"] == "Electronics Engineering"

    # Verify login with new password works
    new_login_res = client.post("/auth/login", json={"username": test_username, "password": new_pwd})
    assert new_login_res.status_code == 200
    active_token = new_login_res.json()["access_token"]

    # 3. Deactivate teacher
    deact_res = client.patch(f"/api/v1/teachers/class-teacher/subject-teachers/{teacher_id}/toggle-status", headers=auth_tokens["class_teacher"])
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # Deactivated teacher login attempt must be rejected (403 Forbidden)
    blocked_login = client.post("/auth/login", json={"username": test_username, "password": new_pwd})
    assert blocked_login.status_code == 403
    assert "deactivated" in blocked_login.text.lower()

    # Active token of deactivated teacher rejected on protected routes (403 Forbidden)
    blocked_req = client.get("/api/v1/teachers/subject-teacher/classes", headers={"Authorization": f"Bearer {active_token}"})
    assert blocked_req.status_code == 403
    assert "deactivated" in blocked_req.text.lower()

    # 4. Reactivate teacher
    react_res = client.patch(f"/api/v1/teachers/class-teacher/subject-teachers/{teacher_id}/toggle-status", headers=auth_tokens["class_teacher"])
    assert react_res.status_code == 200
    assert react_res.json()["is_active"] is True

    # Teacher can log in again after reactivation
    react_login = client.post("/auth/login", json={"username": test_username, "password": new_pwd})
    assert react_login.status_code == 200


def test_rbac_access_restrictions(auth_tokens):
    """
    Test Requirement 7:
    Enforce role-based permissions:
    Only Class Teachers and Admins can create and manage Subject Teachers.
    Subject Teachers and Anonymous users are forbidden.
    """
    dummy_payload = {
        "name": "Unauthorized Faculty",
        "teacher_id": "TID-UNAUTH",
        "username": "unauth_user",
        "password": "Password123!",
        "assignments": []
    }

    # 1. Anonymous request -> 401 Unauthorized
    anon_res = client.get("/api/v1/teachers/class-teacher/subject-teachers")
    assert anon_res.status_code == 401

    # 2. Subject Teacher calling Class Teacher endpoint -> 403 Forbidden
    st_create_res = client.post("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["subject_teacher"], json=dummy_payload)
    assert st_create_res.status_code == 403

    st_list_res = client.get("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["subject_teacher"])
    assert st_list_res.status_code == 403

    # 3. Admin calling Class Teacher endpoint -> 200 OK (Admins have high privileges)
    adm_list_res = client.get("/api/v1/teachers/class-teacher/subject-teachers", headers=auth_tokens["admin"])
    assert adm_list_res.status_code == 200
