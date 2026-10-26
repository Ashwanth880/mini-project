import sys
from pathlib import Path
import requests

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

BASE = 'http://127.0.0.1:8000'


def get_client():
    """Return live requests session if server is running, otherwise TestClient(app)."""
    try:
        r = requests.get(f"{BASE}/health", timeout=1)
        if r.status_code == 200:
            class LiveClient:
                def post(self, path, **kwargs):
                    url = f"{BASE}{path}" if path.startswith('/') else f"{BASE}/{path}"
                    return requests.post(url, **kwargs)
                def get(self, path, **kwargs):
                    url = f"{BASE}{path}" if path.startswith('/') else f"{BASE}/{path}"
                    return requests.get(url, **kwargs)
            return LiveClient()
    except Exception:
        pass
    return TestClient(app)


def run_filters_verification():
    client = get_client()

    # Admin test with filters
    res = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    token = res.json()['access_token']
    admin_headers = {'Authorization': f'Bearer {token}'}

    # Filter by class_id=1
    r1 = client.get('/attendance/dashboard/admin?class_id=1', headers=admin_headers)
    print('Admin filter class_id=1:', r1.status_code, 'Filtered classes:', len(r1.json()['all_classes']), 'Rate:', r1.json()['statistics']['overall_attendance_rate'])

    # Filter by date range
    r2 = client.get('/attendance/dashboard/admin?start_date=2026-10-01&end_date=2026-10-10', headers=admin_headers)
    print('Admin filter date range:', r2.status_code, 'Dates:', len(r2.json()['date_wise']))

    # Subject Teacher filter by subject_id=1
    res_st = client.post('/auth/login', json={'username': 'patel', 'password': 'teacher123'})
    token_st = res_st.json()['access_token']
    st_headers = {'Authorization': f'Bearer {token_st}'}
    r3 = client.get('/attendance/dashboard/subject-teacher?subject_id=1', headers=st_headers)
    print('Subject Teacher filter subject_id=1:', r3.status_code, 'Sessions:', r3.json()['summary']['total_sessions_taken'])

    # Class Teacher filter by student_id=1
    res_ct = client.post('/auth/login', json={'username': 'sharma', 'password': 'teacher123'})
    token_ct = res_ct.json()['access_token']
    ct_headers = {'Authorization': f'Bearer {token_ct}'}
    r4 = client.get('/attendance/dashboard/class-teacher?student_id=1', headers=ct_headers)
    print('Class Teacher filter student_id=1:', r4.status_code, 'Student count:', len(r4.json()['student_wise']), 'Rate:', r4.json()['overall']['attendance_rate'])


if __name__ == '__main__':
    run_filters_verification()
