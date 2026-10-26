import sys
from pathlib import Path
import requests
from datetime import date, timedelta

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

BASE_URL = "http://127.0.0.1:8000"


def get_client():
    """Return live requests session if server is running, otherwise TestClient(app)."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=1)
        if r.status_code == 200:
            class LiveClient:
                def post(self, path, **kwargs):
                    url = path if path.startswith("http") else f"{BASE_URL}{path}"
                    return requests.post(url, **kwargs)
                def get(self, path, **kwargs):
                    url = path if path.startswith("http") else f"{BASE_URL}{path}"
                    return requests.get(url, **kwargs)
            return LiveClient()
    except Exception:
        pass
    return TestClient(app)


def run_tests():
    print("=== STARTING COMPREHENSIVE ATTENDANCE DASHBOARD VERIFICATION ===")
    client = get_client()

    # -------------------------------------------------------------
    # 1. ADMIN DASHBOARD TESTS
    # -------------------------------------------------------------
    print("\n[1] Testing Admin Attendance Dashboard (/attendance/dashboard/admin)...")
    res_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.text}"
    admin_token = res_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 1.1 Default
    r = client.get("/attendance/dashboard/admin", headers=admin_headers)
    assert r.status_code == 200, f"Admin default failed: {r.status_code} {r.text}"
    data = r.json()
    assert "all_classes" in data, "Missing all_classes"
    assert "all_subjects" in data, "Missing all_subjects"
    assert "statistics" in data, "Missing statistics"
    assert "teacher_activity" in data, "Missing teacher_activity"
    assert "date_wise" in data, "Missing date_wise"
    print(f"  [PASS] Admin default: 200 OK | classes: {len(data['all_classes'])}, subjects: {len(data['all_subjects'])}, teachers: {len(data['teacher_activity'])}, overall rate: {data['statistics']['overall_attendance_rate']}%")

    # 1.2 Filter by class_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?class_id=1", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin filter class_id=1: 200 OK | classes: {len(r.json()['all_classes'])}")

    # 1.3 Filter by subject_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?subject_id=1", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin filter subject_id=1: 200 OK | subjects: {len(r.json()['all_subjects'])}")

    # 1.4 Filter by teacher_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?teacher_id=3", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin filter teacher_id=3: 200 OK | teachers: {len(r.json()['teacher_activity'])}")

    # 1.5 Filter by student (string search & roll number)
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?student=21CS001", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin filter student='21CS001': 200 OK | total records: {r.json()['statistics']['total_attendance_records']}")

    # 1.6 Filter by date range
    today_str = str(date.today())
    past_str = str(date.today() - timedelta(days=30))
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?start_date={past_str}&end_date={today_str}", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin filter date range: 200 OK | dates: {len(r.json()['date_wise'])}")

    # 1.7 Combined filters
    r = client.get(f"{BASE_URL}/attendance/dashboard/admin?class_id=1&subject_id=1&start_date={past_str}&end_date={today_str}", headers=admin_headers)
    assert r.status_code == 200
    print(f"  [PASS] Admin combined filters: 200 OK")

    # -------------------------------------------------------------
    # 2. CLASS TEACHER DASHBOARD TESTS
    # -------------------------------------------------------------
    print("\n[2] Testing Class Teacher Attendance Dashboard (/attendance/dashboard/class-teacher)...")
    res_ct = client.post(f"{BASE_URL}/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert res_ct.status_code == 200, f"Class teacher login failed: {res_ct.text}"
    ct_token = res_ct.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    # 2.1 Default
    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher", headers=ct_headers)
    assert r.status_code == 200, f"Class teacher default failed: {r.status_code} {r.text}"
    data = r.json()
    assert "today" in data, "Missing today"
    assert "overall" in data, "Missing overall"
    assert "student_wise" in data, "Missing student_wise"
    assert "subject_wise" in data, "Missing subject_wise"
    assert "date_wise" in data, "Missing date_wise"
    print(f"  [PASS] Class Teacher default: 200 OK | students: {len(data['student_wise'])}, subjects: {len(data['subject_wise'])}, overall rate: {data['overall']['attendance_rate']}%")

    # 2.2 Filter by subject_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher?subject_id=1", headers=ct_headers)
    assert r.status_code == 200
    print(f"  [PASS] Class Teacher filter subject_id=1: 200 OK | subjects: {len(r.json()['subject_wise'])}")

    # 2.3 Filter by student (ID and string)
    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher?student_id=1", headers=ct_headers)
    assert r.status_code == 200
    print(f"  [PASS] Class Teacher filter student_id=1: 200 OK | students: {len(r.json()['student_wise'])}")

    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher?student=Sharma", headers=ct_headers)
    assert r.status_code == 200
    print(f"  [PASS] Class Teacher filter student='Sharma': 200 OK")

    # 2.4 Filter by teacher_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher?teacher_id=3", headers=ct_headers)
    assert r.status_code == 200
    print(f"  [PASS] Class Teacher filter teacher_id=3: 200 OK")

    # 2.5 Filter by date range
    r = client.get(f"{BASE_URL}/attendance/dashboard/class-teacher?start_date={past_str}&end_date={today_str}", headers=ct_headers)
    assert r.status_code == 200
    print(f"  [PASS] Class Teacher filter date range: 200 OK | dates: {len(r.json()['date_wise'])}")

    # -------------------------------------------------------------
    # 3. SUBJECT TEACHER DASHBOARD TESTS
    # -------------------------------------------------------------
    print("\n[3] Testing Subject Teacher Attendance Dashboard (/attendance/dashboard/subject-teacher)...")
    res_st = client.post(f"{BASE_URL}/auth/login", json={"username": "patel", "password": "teacher123"})
    assert res_st.status_code == 200, f"Subject teacher login failed: {res_st.text}"
    st_token = res_st.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # 3.1 Default
    r = client.get(f"{BASE_URL}/attendance/dashboard/subject-teacher", headers=st_headers)
    assert r.status_code == 200, f"Subject teacher default failed: {r.status_code} {r.text}"
    data = r.json()
    assert "summary" in data, "Missing summary"
    assert "class_wise" in data, "Missing class_wise"
    assert "subject_wise" in data, "Missing subject_wise"
    assert "date_wise" in data, "Missing date_wise"
    assert "recent_sessions" in data, "Missing recent_sessions"
    print(f"  [PASS] Subject Teacher default: 200 OK | sessions taken: {data['summary']['total_sessions_taken']}, classes: {len(data['class_wise'])}, subjects: {len(data['subject_wise'])}")

    # 3.2 Filter by class_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/subject-teacher?class_id=1", headers=st_headers)
    assert r.status_code == 200
    print(f"  [PASS] Subject Teacher filter class_id=1: 200 OK | classes: {len(r.json()['class_wise'])}")

    # 3.3 Filter by subject_id
    r = client.get(f"{BASE_URL}/attendance/dashboard/subject-teacher?subject_id=1", headers=st_headers)
    assert r.status_code == 200
    print(f"  [PASS] Subject Teacher filter subject_id=1: 200 OK | subjects: {len(r.json()['subject_wise'])}")

    # 3.4 Filter by student
    r = client.get(f"{BASE_URL}/attendance/dashboard/subject-teacher?student=21CS001", headers=st_headers)
    assert r.status_code == 200
    print(f"  [PASS] Subject Teacher filter student='21CS001': 200 OK")

    # 3.5 Filter by date range
    r = client.get(f"{BASE_URL}/attendance/dashboard/subject-teacher?start_date={past_str}&end_date={today_str}", headers=st_headers)
    assert r.status_code == 200
    print(f"  [PASS] Subject Teacher filter date range: 200 OK | dates: {len(r.json()['date_wise'])}")

    print("\nSUCCESS: ALL 18 DASHBOARD AND FILTER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
