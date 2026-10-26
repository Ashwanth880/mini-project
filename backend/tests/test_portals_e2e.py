"""
End-to-End Test Suite for Smart College Management:
Teacher Portal and Student Portal Comprehensive Validation.

Covers:
1. Teacher Authentication & Access Control
2. Teacher Portal Endpoints (Dashboard, Classes, Assignments, Online Classes, Timetable, Calendar, Announcements, Study Materials, Performance)
3. Student Authentication & Profile Resolution
4. Student Portal Endpoints (Overview, Attendance, Timetable, Assignments, Grades, Notices, Materials, Events, Notifications, Online Classes)
5. Admin Inspection Capabilities via ?student_id
6. Role Authorization Restrictions
"""
import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def teacher_token():
    res = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert res.status_code == 200, f"Teacher login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def student_token():
    res = client.post("/auth/login", json={"username": "student1", "password": "student123"})
    assert res.status_code == 200, f"Student login failed: {res.text}"
    return res.json()["access_token"]


# ===========================================================================
# 1. TEACHER PORTAL ENDPOINTS
# ===========================================================================

class TestTeacherPortal:
    def test_teacher_dashboard(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/dashboard", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "teacher_name" in data
        assert "role" in data
        assert "assigned_classes" in data
        assert "total_assigned_classes" in data

    def test_teacher_my_classes(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/my-classes", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "classes" in data
        assert isinstance(data["classes"], list)

    def test_teacher_assignments_list(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/assignments", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_teacher_online_classes(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/online-classes", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_teacher_timetable(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/timetable", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "weekly_timetable" in data

    def test_teacher_calendar(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/calendar", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "calendar" in data

    def test_teacher_announcements(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/announcements", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_teacher_study_materials(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/study-materials", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_teacher_student_performance(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/student-performance", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "performance" in data
        assert "total_students" in data

    def test_teacher_performance_alias(self, teacher_token):
        headers = {"Authorization": f"Bearer {teacher_token}"}
        res = client.get("/api/v1/teacher-portal/performance", headers=headers)
        assert res.status_code == 200


# ===========================================================================
# 2. STUDENT PORTAL ENDPOINTS
# ===========================================================================

class TestStudentPortal:
    def test_student_profile(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "student" in data
        assert "class_info" in data
        assert "quick_stats" in data
        assert data["student"]["roll_number"] == "21CS001"

    def test_student_attendance_summary(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/attendance", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "overall" in data
        assert "subject_breakdown" in data
        assert "monthly_trend" in data
        assert data["overall"]["percentage"] >= 0

    def test_student_timetable(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/timetable", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "timetable" in data

    def test_student_assignments_list(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/assignments", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "pending" in data
        assert "submitted" in data
        assert "graded" in data

    def test_student_grades(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/grades", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "semesters" in data
        assert "overall_performance" in data

    def test_student_announcements(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/announcements", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "announcements" in data

    def test_student_materials(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/materials", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "materials" in data

    def test_student_events(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/events", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "events" in data

    def test_student_notifications(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/notifications", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "notifications" in data

    def test_student_online_classes(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/online-classes", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "upcoming" in data

    def test_student_dashboard_summary(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/dashboard-summary", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "student" in data
        assert "quick_stats" in data

    def test_student_dashboard_alias(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/student-portal/dashboard", headers=headers)
        assert res.status_code == 200


# ===========================================================================
# 3. RBAC & ADMIN CROSS-INSPECTION
# ===========================================================================

class TestRoleAuthorization:
    def test_student_cannot_access_teacher_portal(self, student_token):
        headers = {"Authorization": f"Bearer {student_token}"}
        res = client.get("/api/v1/teacher-portal/dashboard", headers=headers)
        assert res.status_code == 403

    def test_admin_can_inspect_student_portal(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.get("/api/v1/student-portal/me?student_id=1", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["student"]["id"] == 1

    def test_admin_can_access_teacher_portal(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.get("/api/v1/teacher-portal/dashboard", headers=headers)
        assert res.status_code == 200
