"""
Frontend and Browser Integration Test Suite for One-Click Attendance.

Verifies:
1. Static asset serving (HTML5 application root, CSS stylesheets, JavaScript client bundles)
2. Complete DOM hierarchy, element IDs, form bindings, and modal dialogs
3. Role-based navigation and UI visibility scoping (Admin vs Class Teacher vs Subject Teacher)
4. Frontend-backend API contract integrity (Auth, Dashboard, Admin, Students, Attendance, Reports)
5. Interactive UI workflow simulation mimicking browser fetch calls and state transitions
"""

import sys
import json
import re
from pathlib import Path
from html.parser import HTMLParser

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class SimpleDOMParser(HTMLParser):
    """Parses HTML and collects tags, IDs, classes, and data-* attributes."""
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = {}
        self.classes = set()
        self.data_targets = set()
        self.role_nav_items = []
        self._current_role_req = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attr_dict = dict(attrs)
        
        elem_id = attr_dict.get("id")
        if elem_id:
            self.ids[elem_id] = tag

        elem_class = attr_dict.get("class")
        if elem_class:
            for cls in elem_class.split():
                self.classes.add(cls)

        if "data-role-req" in attr_dict:
            self._current_role_req = attr_dict["data-role-req"]

        target = attr_dict.get("data-target")
        if target:
            self.data_targets.add(target)
            if self._current_role_req:
                self.role_nav_items.append((self._current_role_req, target))

    def handle_endtag(self, tag):
        if tag == "li" and self._current_role_req:
            self._current_role_req = None


def test_01_static_assets_serving():
    """Verify HTML entry point, stylesheet, and JS client bundles are served correctly."""
    # 1. Main HTML document
    res_html = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert res_html.status_code == 200, f"Root HTML returned {res_html.status_code}"
    assert "text/html" in res_html.headers.get("content-type", "")
    html_content = res_html.text
    assert "<!DOCTYPE html>" in html_content or "<!doctype html>" in html_content
    assert "<title>One-Click Attendance System" in html_content

    # Also verify direct static mount
    res_static_html = client.get("/static/index.html")
    assert res_static_html.status_code == 200

    # 2. Stylesheet
    res_css = client.get("/css/styles.css")
    assert res_css.status_code == 200, f"Stylesheet returned {res_css.status_code}"
    assert len(res_css.text) > 100
    assert "sidebar" in res_css.text or "auth-wrapper" in res_css.text

    # 3. JavaScript API bundle
    res_api = client.get("/js/api.js")
    assert res_api.status_code == 200, f"API script returned {res_api.status_code}"
    assert "class ApiClient" in res_api.text or "ApiClient" in res_api.text or "fetch(" in res_api.text

    # 4. JavaScript Main App bundle
    res_app = client.get("/js/app.js")
    assert res_app.status_code == 200, f"App script returned {res_app.status_code}"
    assert len(res_app.text) > 500


def test_02_dom_structure_and_element_ids():
    """Verify all critical UI views, form fields, and action buttons are present in HTML."""
    res = client.get("/", headers={"Accept": "text/html"})
    assert res.status_code == 200
    parser = SimpleDOMParser()
    parser.feed(res.text)

    # Required Authentication Form IDs
    required_auth_ids = [
        "auth-container",
        "auth-alert",
        "login-form",
        "login-username",
        "login-password",
        "btn-login-submit",
        "register-form",
        "reg-fullname",
        "reg-username",
        "reg-role",
        "reg-email",
        "reg-pwd",
        "toggle-to-register",
        "toggle-to-login",
    ]
    for auth_id in required_auth_ids:
        assert auth_id in parser.ids, f"Required auth element id '{auth_id}' missing in HTML!"

    # Required Main Application and Navigation IDs
    required_app_ids = [
        "app-container",
        "sidebar-toggle",
        "current-section-title",
        "api-status-badge",
        "api-status-text",
        "header-user-name",
        "header-user-role",
        "btn-logout",
    ]
    for app_id in required_app_ids:
        assert app_id in parser.ids, f"Required app container element id '{app_id}' missing in HTML!"

    # Required Core Views via data-target
    expected_views = {
        "dashboard-section",
        "admin-section",
        "class-teacher-section",
        "subject-teacher-section",
        "student-mgmt-section",
        "one-click-section",
        "reports-section",
    }
    assert expected_views.issubset(parser.data_targets), f"Missing data-targets: {expected_views - parser.data_targets}"


def test_03_role_based_navigation_rules():
    """Verify role requirements metadata matches the system RBAC specification."""
    res = client.get("/", headers={"Accept": "text/html"})
    parser = SimpleDOMParser()
    parser.feed(res.text)

    # Check the data-role-req constraints on navigation links
    admin_targets = [target for role, target in parser.role_nav_items if role == "ADMIN"]
    class_teacher_targets = [target for role, target in parser.role_nav_items if "CLASS_TEACHER" in role]
    all_targets = [target for role, target in parser.role_nav_items if role == "ALL"]

    assert "admin-section" in admin_targets, "Admin portal must require ADMIN role"
    assert any("class-teacher-section" in s for s in class_teacher_targets), "Class Teacher portal must require CLASS_TEACHER or ADMIN role"
    assert "dashboard-section" in all_targets, "Dashboard must be accessible by ALL authenticated users"
    assert "reports-section" in all_targets, "Reports must be accessible by ALL authenticated users"
    assert "one-click-section" in all_targets, "One-Click attendance must be accessible by ALL authenticated users"


def test_04_frontend_api_authentication_workflow():
    """Simulate the browser login flow and error handling."""
    # 1. Invalid credentials -> verify 401 and error detail
    res_bad = client.post("/auth/login", json={"username": "nonexistent_user", "password": "wrongpassword"})
    assert res_bad.status_code == 401
    bad_data = res_bad.json()
    assert "detail" in bad_data
    assert "Invalid username or password" in bad_data["detail"]

    # 2. Valid Admin Login
    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_admin.status_code == 200
    admin_data = res_admin.json()
    assert "access_token" in admin_data
    assert admin_data.get("token_type") == "bearer"
    role = admin_data.get("role") or admin_data.get("user", {}).get("role")
    assert role == "ADMIN"
    admin_token = admin_data["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Verify user profile endpoint returns full details for the frontend user badge
    res_me = client.get("/auth/me", headers=admin_headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["username"] == "admin"
    assert me_data["role"] == "ADMIN"
    assert "full_name" in me_data

    # 4. Valid Class Teacher Login
    res_ct = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert res_ct.status_code == 200
    ct_data = res_ct.json()
    ct_role = ct_data.get("role") or ct_data.get("user", {}).get("role")
    assert ct_role == "CLASS_TEACHER"

    # 5. Valid Subject Teacher Login
    res_st = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert res_st.status_code == 200
    st_data = res_st.json()
    st_role = st_data.get("role") or st_data.get("user", {}).get("role")
    assert st_role == "SUBJECT_TEACHER"


def test_05_frontend_dashboard_and_portal_data_binding():
    """Verify that all APIs consumed by frontend dashboard, portals, and reports respond with expected schema."""
    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

    # Dashboard stats
    res_stats = client.get("/api/v1/admin/dashboard-stats", headers=admin_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    expected_stat_keys = {"total_students", "total_classes", "total_subjects", "total_teachers"}
    assert expected_stat_keys.issubset(set(stats.keys()))

    # Admin portal: Classes list
    res_classes = client.get("/api/v1/admin/classes", headers=admin_headers)
    assert res_classes.status_code == 200
    classes = res_classes.json()
    assert isinstance(classes, list)
    if classes:
        assert "name" in classes[0] and "department" in classes[0]

    # Admin portal: Subjects list
    res_subjects = client.get("/api/v1/admin/subjects", headers=admin_headers)
    assert res_subjects.status_code == 200
    subjects = res_subjects.json()
    assert isinstance(subjects, list)
    if subjects:
        assert "code" in subjects[0] and "name" in subjects[0]

    # Admin portal: Teachers list
    res_teachers = client.get("/api/v1/admin/teachers", headers=admin_headers)
    assert res_teachers.status_code == 200
    teachers = res_teachers.json()
    assert isinstance(teachers, list)
    if teachers:
        assert "full_name" in teachers[0] and "role" in teachers[0]

    # Subject teacher classes binding
    res_st = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    st_headers = {"Authorization": f"Bearer {res_st.json()['access_token']}"}
    res_st_portal = client.get("/api/v1/teachers/subject-teacher/classes", headers=st_headers)
    assert res_st_portal.status_code == 200
    st_portal = res_st_portal.json()
    assert "assigned_subjects" in st_portal
    assert "available_classes" in st_portal

    # Class teacher my-class binding
    res_ct = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    ct_headers = {"Authorization": f"Bearer {res_ct.json()['access_token']}"}
    res_ct_portal = client.get("/api/v1/teachers/class-teacher/my-class", headers=ct_headers)
    assert res_ct_portal.status_code == 200
    ct_portal = res_ct_portal.json()
    assert "id" in ct_portal and "name" in ct_portal


def test_06_frontend_reports_and_csv_export():
    """Verify all report views consumed by frontend tables and Chart.js respond with correct schemas and CSV downloads."""
    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

    # 1. Daily Report
    res_daily = client.get("/api/v1/attendance/reports/daily?date=2026-10-05", headers=admin_headers)
    assert res_daily.status_code == 200
    daily_data = res_daily.json()
    assert "report_type" in daily_data or "date" in daily_data
    assert "records" in daily_data or "summary" in daily_data

    # 2. Student Report
    res_student = client.get("/api/v1/attendance/reports/student?student_id=1", headers=admin_headers)
    assert res_student.status_code == 200
    student_data = res_student.json()
    assert "report_type" in student_data or "student_id" in student_data or "records" in student_data

    # 3. Class Report
    res_class = client.get("/api/v1/attendance/reports/class?class_id=1", headers=admin_headers)
    assert res_class.status_code == 200
    class_data = res_class.json()
    assert "report_type" in class_data or "class_id" in class_data or "records" in class_data

    # 4. Subject Report
    res_subj = client.get("/api/v1/attendance/reports/subject?subject_id=1", headers=admin_headers)
    assert res_subj.status_code == 200
    subj_data = res_subj.json()
    assert "report_type" in subj_data or "subject_id" in subj_data or "records" in subj_data

    # 5. Monthly Report
    res_month = client.get("/api/v1/attendance/reports/monthly?year=2026&month=10", headers=admin_headers)
    assert res_month.status_code == 200
    month_data = res_month.json()
    assert "report_type" in month_data or "records" in month_data or "summary" in month_data

    # 6. CSV Export endpoint
    res_csv = client.get("/api/v1/attendance/reports/export-csv?report_type=daily&date=2026-10-05", headers=admin_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type", "")
    assert "attachment" in res_csv.headers.get("content-disposition", "")
    assert len(res_csv.text) > 0


if __name__ == "__main__":
    test_01_static_assets_serving()
    test_02_dom_structure_and_element_ids()
    test_03_role_based_navigation_rules()
    test_04_frontend_api_authentication_workflow()
    test_05_frontend_dashboard_and_portal_data_binding()
    test_06_frontend_reports_and_csv_export()
    print("All frontend integration tests passed successfully!")
