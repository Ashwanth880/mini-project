"""
Test Suite for Attendance Reports & Analytics Verification.
Tests:
1. Daily attendance report
2. Student attendance report
3. Subject attendance report
4. Class attendance report
5. Monthly attendance report
6. CSV Export generation & endpoints
7. Calculations: Present count, Absent count, Total classes, Attendance percentage
8. Date-range and contextual filtering
"""

import sys
import os
from pathlib import Path
from datetime import date, timedelta

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.services.reports_service import reports_service
from app.models.attendance import Attendance, AttendanceStatus

def run_tests():
    print("=" * 70)
    print("RUNNING ATTENDANCE REPORTS VERIFICATION SUITE")
    print("=" * 70)

    db = SessionLocal()
    client = TestClient(app)

    # Inspect total stored attendance records in DB
    total_db_records = db.query(Attendance).count()
    present_db_records = db.query(Attendance).filter(Attendance.status == AttendanceStatus.PRESENT).count()
    absent_db_records = total_db_records - present_db_records
    expected_pct = round((present_db_records / total_db_records * 100.0), 2) if total_db_records > 0 else 0.0

    print(f"\n[Database Inspection]")
    print(f"Total stored attendance records: {total_db_records}")
    print(f"Present records: {present_db_records}")
    print(f"Absent records: {absent_db_records}")
    print(f"Calculated percentage: {expected_pct}%")

    dates = [r.date for r in db.query(Attendance.date).distinct().all()]
    print(f"Dates with attendance: {dates}")

    # Authenticate as Admin
    res_login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_login.status_code == 200
    headers = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    # -------------------------------------------------------------
    # 1. Daily Attendance Report Test
    # -------------------------------------------------------------
    print("\n--- 1. Testing Daily Attendance Report ---")
    daily_res = client.get("/api/v1/attendance/reports/daily", headers=headers)
    assert daily_res.status_code == 200, f"Daily report failed: {daily_res.text}"
    daily_data = daily_res.json()
    assert daily_data["report_type"] == "daily"
    summary = daily_data["summary"]

    print(f"Daily summary: total_classes={summary['total_classes']}, present={summary['present_count']}, absent={summary['absent_count']}, pct={summary['attendance_percentage']}%")
    assert summary["present_count"] == present_db_records
    assert summary["absent_count"] == absent_db_records
    assert summary["total_records"] == total_db_records
    assert summary["attendance_percentage"] == expected_pct
    assert len(daily_data["rows"]) == len(dates)
    print(">>> Daily Report: PASSED (Exact stored record match & percentage calculation verified)")

    # -------------------------------------------------------------
    # 2. Student Attendance Report Test
    # -------------------------------------------------------------
    print("\n--- 2. Testing Student Attendance Report ---")
    student_res = client.get("/api/v1/attendance/reports/student", headers=headers)
    assert student_res.status_code == 200, f"Student report failed: {student_res.text}"
    student_data = student_res.json()
    assert student_data["report_type"] == "student"
    s_summary = student_data["summary"]

    print(f"Student summary: total_students={s_summary['total_students']}, present={s_summary['present_count']}, absent={s_summary['absent_count']}, eligible={s_summary['eligible_count']}, shortage={s_summary['shortage_count']}")
    assert s_summary["present_count"] == present_db_records
    assert s_summary["absent_count"] == absent_db_records
    assert s_summary["attendance_percentage"] == expected_pct

    # Verify per-student calculation
    for row in student_data["rows"]:
        s_pres = row["present_count"]
        s_abs = row["absent_count"]
        s_tot = row["total_classes"]
        s_pct = row["attendance_percentage"]
        assert s_pres + s_abs == s_tot
        if s_tot > 0:
            assert abs(s_pct - round(s_pres / s_tot * 100.0, 2)) < 0.01
            assert (row["status_label"] == "Eligible") == (s_pct >= 75.0)
    print(f">>> Student Report: PASSED ({len(student_data['rows'])} students calculated correctly)")

    # -------------------------------------------------------------
    # 3. Subject Attendance Report Test
    # -------------------------------------------------------------
    print("\n--- 3. Testing Subject Attendance Report ---")
    subject_res = client.get("/api/v1/attendance/reports/subject", headers=headers)
    assert subject_res.status_code == 200, f"Subject report failed: {subject_res.text}"
    subject_data = subject_res.json()
    assert subject_data["report_type"] == "subject"
    sub_summary = subject_data["summary"]

    print(f"Subject summary: total_subjects={sub_summary['total_subjects']}, total_classes={sub_summary['total_classes']}, present={sub_summary['present_count']}, absent={sub_summary['absent_count']}, pct={sub_summary['attendance_percentage']}%")
    assert sub_summary["present_count"] == present_db_records
    assert sub_summary["absent_count"] == absent_db_records
    assert sub_summary["attendance_percentage"] == expected_pct

    for row in subject_data["rows"]:
        assert row["present_count"] + row["absent_count"] == row["total_records"]
        if row["total_records"] > 0:
            calc = round(row["present_count"] / row["total_records"] * 100.0, 2)
            assert abs(row["attendance_percentage"] - calc) < 0.01
    print(f">>> Subject Report: PASSED ({len(subject_data['rows'])} subjects checked)")

    # -------------------------------------------------------------
    # 4. Class Attendance Report Test
    # -------------------------------------------------------------
    print("\n--- 4. Testing Class Attendance Report ---")
    class_res = client.get("/api/v1/attendance/reports/class", headers=headers)
    assert class_res.status_code == 200, f"Class report failed: {class_res.text}"
    class_data = class_res.json()
    assert class_data["report_type"] == "class"
    c_summary = class_data["summary"]

    print(f"Class summary: total_classes_count={c_summary['total_classes_count']}, conducted_sessions={c_summary['total_classes']}, present={c_summary['present_count']}, absent={c_summary['absent_count']}")
    assert c_summary["present_count"] == present_db_records
    assert c_summary["absent_count"] == absent_db_records
    assert c_summary["attendance_percentage"] == expected_pct

    for row in class_data["rows"]:
        assert row["present_count"] + row["absent_count"] == row["total_records"]
        if row["total_records"] > 0:
            calc = round(row["present_count"] / row["total_records"] * 100.0, 2)
            assert abs(row["attendance_percentage"] - calc) < 0.01
    print(f">>> Class Report: PASSED ({len(class_data['rows'])} classes checked)")

    # -------------------------------------------------------------
    # 5. Monthly Attendance Report Test
    # -------------------------------------------------------------
    print("\n--- 5. Testing Monthly Attendance Report ---")
    monthly_res = client.get("/api/v1/attendance/reports/monthly", headers=headers)
    assert monthly_res.status_code == 200, f"Monthly report failed: {monthly_res.text}"
    monthly_data = monthly_res.json()
    assert monthly_data["report_type"] == "monthly"
    m_summary = monthly_data["summary"]

    print(f"Monthly summary: total_months={m_summary['total_months']}, working_days={m_summary['working_days_count']}, total_classes={m_summary['total_classes']}, pct={m_summary['attendance_percentage']}%")
    assert m_summary["present_count"] == present_db_records
    assert m_summary["absent_count"] == absent_db_records
    assert m_summary["attendance_percentage"] == expected_pct

    for row in monthly_data["rows"]:
        assert row["present_count"] + row["absent_count"] == row["total_records"]
        if row["total_records"] > 0:
            calc = round(row["present_count"] / row["total_records"] * 100.0, 2)
            assert abs(row["attendance_percentage"] - calc) < 0.01
    print(f">>> Monthly Report: PASSED ({len(monthly_data['rows'])} months checked)")

    # -------------------------------------------------------------
    # 6. Date-Range Filtering Test
    # -------------------------------------------------------------
    print("\n--- 6. Testing Date-Range Filtering ---")
    if dates:
        test_date = dates[0]
        # Filter for exact date
        filtered_res = client.get(f"/api/v1/attendance/reports/daily?start_date={test_date}&end_date={test_date}", headers=headers)
        assert filtered_res.status_code == 200
        f_data = filtered_res.json()
        assert len(f_data["rows"]) == 1
        assert f_data["rows"][0]["date"] == str(test_date)
        print(f"Filtered for single date {test_date}: {f_data['rows'][0]['total_records']} records matched")

        # Future date with zero records
        future_date = date.today() + timedelta(days=365)
        empty_res = client.get(f"/api/v1/attendance/reports/daily?start_date={future_date}&end_date={future_date}", headers=headers)
        assert empty_res.status_code == 200
        e_data = empty_res.json()
        assert len(e_data["rows"]) == 0
        assert e_data["summary"]["total_records"] == 0
        assert e_data["summary"]["attendance_percentage"] == 0.0
        print(f"Filtered for empty future date {future_date}: 0 records returned gracefully")

    print(">>> Date-Range Filtering: PASSED")

    # -------------------------------------------------------------
    # 7. CSV Export Tests
    # -------------------------------------------------------------
    print("\n--- 7. Testing CSV Export for All 5 Reports ---")
    for r_type in ["daily", "student", "subject", "class", "monthly"]:
        # Test query parameter format=csv on dedicated endpoint
        csv_res1 = client.get(f"/api/v1/attendance/reports/{r_type}?format=csv", headers=headers)
        assert csv_res1.status_code == 200, f"CSV export via format=csv failed for {r_type}"
        assert "text/csv" in csv_res1.headers["content-type"]
        assert f"filename=" in csv_res1.headers["content-disposition"]
        csv_text = csv_res1.text
        assert "ONE-CLICK ATTENDANCE SYSTEM" in csv_text
        assert "Attendance Percentage" in csv_text or "Attendance Rate" in csv_text or "%" in csv_text

        # Test export-csv dispatcher endpoint
        csv_res2 = client.get(f"/api/v1/attendance/reports/export-csv?report_type={r_type}", headers=headers)
        assert csv_res2.status_code == 200, f"CSV export via export-csv failed for {r_type}"
        assert "text/csv" in csv_res2.headers["content-type"]
        print(f"CSV Export for '{r_type}' verified ({len(csv_text.splitlines())} lines).")

    print(">>> CSV Export for all 5 reports: PASSED")

    # -------------------------------------------------------------
    # 8. Unified Reports Dispatcher Test
    # -------------------------------------------------------------
    print("\n--- 8. Testing Unified /reports Dispatcher ---")
    disp_res = client.get("/api/v1/attendance/reports?report_type=daily", headers=headers)
    assert disp_res.status_code == 200
    assert disp_res.json()["report_type"] == "daily"

    disp_res_csv = client.get("/api/v1/attendance/reports?report_type=student&format=csv", headers=headers)
    assert disp_res_csv.status_code == 200
    assert "text/csv" in disp_res_csv.headers["content-type"]
    print(">>> Unified Dispatcher: PASSED")

    db.close()
    print("\n" + "=" * 70)
    print("ALL 8 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


def test_reports_verification():
    """Pytest entrypoint for reports verification."""
    run_tests()


if __name__ == "__main__":
    run_tests()
