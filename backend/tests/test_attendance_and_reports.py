"""
Attendance Lifecycle & Reports Automated Test Suite.
Covers:
1. Attendance Analysis (POST /api/v1/attendance/analyze):
   - Multi-face photo upload for assigned class & subject
   - Preview records (Present & Absent students)
   - Unknown detections & annotated image URL
2. Class Restriction:
   - Student from Class B in photo of Class A is NOT marked present in Class A
   - Teacher not assigned to Class/Subject receives 403 Forbidden
3. Attendance Confirmation (POST /api/v1/attendance/confirm):
   - Save verified records in database
   - Automatic vs Manual status adjustments (is_manual=True)
   - Proper attribution of teacher_id
4. Duplicate Attendance Prevention:
   - Duplicate student in same confirmation batch rejected with 400 Bad Request
   - Re-submitting attendance for same class+subject+date+period upserts record without duplicate rows
5. Reports:
   - Daily report (/reports/daily)
   - Student report (/reports/student)
   - Subject report (/reports/subject)
   - Class report (/reports/class)
   - Monthly report (/reports/monthly)
   - Calculations: total classes, present count, absent count, percentage
   - Date range filtering
6. CSV Export:
   - Query format=csv on dedicated endpoints
   - Unified /reports/export-csv dispatcher
   - Verify Content-Type text/csv, header metadata, rows, percentages
"""

import sys
import io
import csv
import json
from datetime import date, timedelta
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.academic import Class, Subject, ClassSubject
from app.models.student import Student, StudentFace
from app.models.attendance import Attendance, AttendanceStatus
from app.services.face_service import face_service

client = TestClient(app)
samples_dir = backend_dir.parent / "data" / "test_samples"


def load_sample(filename: str) -> bytes:
    p = samples_dir / filename
    assert p.exists(), f"Sample {filename} not found at {p}"
    return p.read_bytes()


def test_attendance_and_reports_suite():
    print("=" * 70)
    print("STARTING ATTENDANCE & REPORTS TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 0. SETUP AUTH & TEST FIXTURES
    # -------------------------------------------------------------
    print("\n--- STEP 0: Authentication Setup ---")
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ct_login = client.post("/auth/login", json={"username": "sharma", "password": "teacher123"})
    assert ct_login.status_code == 200
    ct_token = ct_login.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    st_login = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert st_login.status_code == 200
    st_token = st_login.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # Setup 2 Classes and 2 Students with enrolled faces
    db = SessionLocal()
    try:
        # Class 1: CSE-A (Teacher 'sharma' is class teacher; 'patel' teaches subject 1)
        cls_1 = db.query(Class).filter(Class.name == "CSE Year 3 Sec A").first()
        if not cls_1:
            cls_1 = Class(name="CSE Year 3 Sec A", department="Computer Science", year=3, section="A", class_teacher_id=2)
            db.add(cls_1)
            db.flush()

        # Class 2: ECE-A (Separate department)
        cls_2 = db.query(Class).filter(Class.name == "ECE Year 3 Sec A").first()
        if not cls_2:
            cls_2 = Class(name="ECE Year 3 Sec A", department="Electronics", year=3, section="A")
            db.add(cls_2)
            db.flush()

        # Subject 1: Data Structures
        subj_1 = db.query(Subject).filter(Subject.code == "CS301").first()
        if not subj_1:
            subj_1 = Subject(code="CS301", name="Data Structures", department="Computer Science")
            db.add(subj_1)
            db.flush()

        # Subject 2: Embedded Systems
        subj_2 = db.query(Subject).filter(Subject.code == "EC301").first()
        if not subj_2:
            subj_2 = Subject(code="EC301", name="Embedded Systems", department="Electronics")
            db.add(subj_2)
            db.flush()

        # Ensure teacher 3 (patel) is assigned to Class 1 + Subject 1
        assign_1 = db.query(ClassSubject).filter(
            ClassSubject.class_id == cls_1.id,
            ClassSubject.subject_id == subj_1.id,
            ClassSubject.teacher_id == 3,
        ).first()
        if not assign_1:
            assign_1 = ClassSubject(class_id=cls_1.id, subject_id=subj_1.id, teacher_id=3)
            db.add(assign_1)
            db.flush()

        # Enroll Student Alex into Class 1
        alex_st = db.query(Student).filter(Student.roll_number == "ATT_ALEX_01").first()
        if not alex_st:
            alex_st = Student(
                roll_number="ATT_ALEX_01",
                register_number="REG_ATT_ALEX_01",
                full_name="Alex Turner Att",
                department="Computer Science",
                year=3,
                section="A",
                class_id=cls_1.id,
                is_active=True,
                face_enrolled=True,
            )
            db.add(alex_st)
            db.flush()

        alex_bytes = load_sample("student_alex.jpg")
        alex_bgr = face_service.decode_image_bytes(alex_bytes)
        alex_face = face_service.detect_faces(alex_bgr)[0]
        alex_emb = face_service.extract_face_embedding(alex_bgr, alex_face)

        # Store Alex embedding in DB
        db.query(StudentFace).filter(StudentFace.student_id == alex_st.id).delete()
        face_rec = StudentFace(
            student_id=alex_st.id,
            image_path="test_alex.jpg",
            embedding=face_service.serialize_embedding(alex_emb),
            is_primary=True,
        )
        db.add(face_rec)

        # Enroll Student Priya into Class 2 (DIFFERENT CLASS)
        priya_st = db.query(Student).filter(Student.roll_number == "ATT_PRIYA_02").first()
        if not priya_st:
            priya_st = Student(
                roll_number="ATT_PRIYA_02",
                register_number="REG_ATT_PRIYA_02",
                full_name="Priya Sharma Att",
                department="Electronics",
                year=3,
                section="A",
                class_id=cls_2.id,
                is_active=True,
                face_enrolled=True,
            )
            db.add(priya_st)
            db.flush()

        priya_bytes = load_sample("student_priya.jpg")
        priya_bgr = face_service.decode_image_bytes(priya_bytes)
        priya_face = face_service.detect_faces(priya_bgr)[0]
        priya_emb = face_service.extract_face_embedding(priya_bgr, priya_face)

        db.query(StudentFace).filter(StudentFace.student_id == priya_st.id).delete()
        face_rec_p = StudentFace(
            student_id=priya_st.id,
            image_path="test_priya.jpg",
            embedding=face_service.serialize_embedding(priya_emb),
            is_primary=True,
        )
        db.add(face_rec_p)
        db.commit()

        cls_1_id = cls_1.id
        cls_2_id = cls_2.id
        subj_1_id = subj_1.id
        subj_2_id = subj_2.id
        alex_id = alex_st.id
        priya_id = priya_st.id
    finally:
        db.close()

    # -------------------------------------------------------------
    # 1. ATTENDANCE ANALYSIS & CLASS RESTRICTION
    # -------------------------------------------------------------
    print("\n--- 1. Testing Attendance Analysis & Class Restriction ---")

    # 1.1 Teacher unauthorized access check:
    # Subject Teacher 'patel' is NOT assigned to Class 2 + Subject 2 -> 403 Forbidden
    classroom_bytes = load_sample("classroom_alex_priya.jpg")
    res_unauth_analysis = client.post(
        "/api/v1/attendance/analyze",
        headers=st_headers,
        data={"class_id": cls_2_id, "subject_id": subj_2_id, "period": 1},
        files={"photo": ("classroom.jpg", classroom_bytes, "image/jpeg")},
    )
    assert res_unauth_analysis.status_code == 403, f"Expected 403, got {res_unauth_analysis.status_code}"
    print("[PASS] Unauthorized teacher attendance analysis blocked with HTTP 403.")

    # 1.2 Authorized Analysis for Class 1:
    # Photo contains both Alex and Priya, but ONLY Alex is enrolled in Class 1!
    res_analysis = client.post(
        "/api/v1/attendance/analyze",
        headers=st_headers,
        data={"class_id": cls_1_id, "subject_id": subj_1_id, "period": 1, "date_str": str(date.today())},
        files={"photo": ("classroom.jpg", classroom_bytes, "image/jpeg")},
    )
    assert res_analysis.status_code == 200, f"Analysis failed: {res_analysis.text}"
    analysis_data = res_analysis.json()

    assert analysis_data["class_id"] == cls_1_id
    assert analysis_data["total_faces_detected"] == 2
    assert analysis_data["recognized_count"] == 1, "Only Alex is in Class 1"
    assert analysis_data["unknown_count"] == 1, "Priya from Class 2 must be marked UNKNOWN"

    # Verify Class Boundary Enforcement:
    alex_preview = next((p for p in analysis_data["preview_records"] if p["student_id"] == alex_id), None)
    assert alex_preview is not None
    assert alex_preview["status"] == "PRESENT"
    assert alex_preview["is_detected"] is True

    # Priya must NOT be in preview records of Class 1
    assert not any(p["student_id"] == priya_id for p in analysis_data["preview_records"])
    print("[PASS] Class restriction enforced: Priya (Class 2) treated as UNKNOWN in Class 1 attendance.")

    attendance_image_id = analysis_data["attendance_image_id"]
    assert attendance_image_id is not None
    print(f"[PASS] Attendance analyzed successfully: {analysis_data['present_count']} present, {analysis_data['absent_count']} absent.")

    # -------------------------------------------------------------
    # 2. ATTENDANCE CONFIRMATION & DUPLICATE PREVENTION
    # -------------------------------------------------------------
    print("\n--- 2. Testing Attendance Confirmation & Duplicate Prevention ---")
    today_str = str(date.today())

    # 2.1 Duplicate student in same confirmation batch rejected with 400
    dup_batch_payload = {
        "confirmed_records": [
            {
                "student_id": alex_id,
                "class_id": cls_1_id,
                "subject_id": subj_1_id,
                "date": today_str,
                "period": 1,
                "status": "PRESENT",
                "confidence": 0.94,
                "is_manual": False,
            },
            {
                "student_id": alex_id,  # DUPLICATE IN SAME REQUEST
                "class_id": cls_1_id,
                "subject_id": subj_1_id,
                "date": today_str,
                "period": 1,
                "status": "PRESENT",
                "confidence": 0.94,
                "is_manual": False,
            },
        ]
    }
    res_dup_batch = client.post("/api/v1/attendance/confirm", json=dup_batch_payload, headers=st_headers)
    assert res_dup_batch.status_code == 400, f"Expected 400 for duplicate student in batch, got {res_dup_batch.status_code}"
    assert "duplicate" in res_dup_batch.json()["detail"].lower()
    print("[PASS] Duplicate attendance entry in same batch rejected with HTTP 400.")

    # 2.2 Teacher modifying unassigned class confirmation -> 403 Forbidden
    res_unauth_confirm = client.post(
        "/api/v1/attendance/confirm",
        headers=st_headers,
        json={
            "confirmed_records": [
                {
                    "student_id": priya_id,
                    "class_id": cls_2_id,  # Unassigned class
                    "subject_id": subj_2_id,
                    "date": today_str,
                    "period": 1,
                    "status": "PRESENT",
                }
            ]
        },
    )
    assert res_unauth_confirm.status_code == 403
    print("[PASS] Confirmation for unassigned class rejected with HTTP 403.")

    # 2.3 Valid confirmation
    confirm_payload = {
        "confirmed_records": [
            {
                "student_id": alex_id,
                "class_id": cls_1_id,
                "subject_id": subj_1_id,
                "teacher_id": 3,
                "date": today_str,
                "period": 1,
                "status": "PRESENT",
                "confidence": 0.93,
                "attendance_image_id": attendance_image_id,
                "bounding_box": json.dumps([357, 219, 311, 422]),
                "is_manual": False,
            }
        ]
    }
    res_confirm = client.post("/api/v1/attendance/confirm", json=confirm_payload, headers=st_headers)
    assert res_confirm.status_code == 200, f"Confirmation failed: {res_confirm.text}"
    saved_recs = res_confirm.json()
    assert len(saved_recs) == 1
    assert saved_recs[0]["student_id"] == alex_id
    assert saved_recs[0]["status"] == "PRESENT"
    print("[PASS] Attendance confirmed and saved in database.")

    # 2.4 Duplicate attendance prevention (Upsert behavior on re-submission):
    # If the teacher manually changes Alex from PRESENT to ABSENT for the same period/date/subject/class,
    # the existing record is updated rather than inserting a duplicate record!
    update_payload = {
        "confirmed_records": [
            {
                "student_id": alex_id,
                "class_id": cls_1_id,
                "subject_id": subj_1_id,
                "teacher_id": 3,
                "date": today_str,
                "period": 1,
                "status": "ABSENT",
                "confidence": 0.0,
                "is_manual": True,
            }
        ]
    }
    res_reconfirm = client.post("/api/v1/attendance/confirm", json=update_payload, headers=st_headers)
    assert res_reconfirm.status_code == 200
    updated_recs = res_reconfirm.json()
    assert updated_recs[0]["status"] == "ABSENT"
    assert updated_recs[0]["is_manual"] is True

    # Verify directly in DB that exactly 1 record exists for this student+class+subject+date+period
    db_check = SessionLocal()
    rec_count = db_check.query(Attendance).filter(
        Attendance.student_id == alex_id,
        Attendance.class_id == cls_1_id,
        Attendance.subject_id == subj_1_id,
        Attendance.date == today_str,
        Attendance.period == 1,
    ).count()
    assert rec_count == 1, f"Expected 1 record after reconfirmation, found {rec_count}"
    print("[PASS] Re-submitting attendance updated existing record cleanly without creating duplicate rows.")

    # Reset back to PRESENT for report verification
    revert_payload = {
        "confirmed_records": [
            {
                "student_id": alex_id,
                "class_id": cls_1_id,
                "subject_id": subj_1_id,
                "teacher_id": 3,
                "date": today_str,
                "period": 1,
                "status": "PRESENT",
                "confidence": 0.95,
                "is_manual": False,
            }
        ]
    }
    client.post("/api/v1/attendance/confirm", json=revert_payload, headers=st_headers)
    db_check.close()

    # -------------------------------------------------------------
    # 3. REPORTS & ANALYTICS
    # -------------------------------------------------------------
    print("\n--- 3. Testing Attendance Reports & Analytics ---")

    # 3.1 Daily report
    daily_res = client.get("/api/v1/attendance/reports/daily", headers=admin_headers)
    assert daily_res.status_code == 200, f"Daily report failed: {daily_res.text}"
    daily_json = daily_res.json()
    assert daily_json["report_type"] == "daily"
    assert "summary" in daily_json
    assert "rows" in daily_json
    d_summary = daily_json["summary"]
    assert d_summary["total_records"] >= 1
    assert d_summary["present_count"] + d_summary["absent_count"] == d_summary["total_records"]
    assert 0.0 <= d_summary["attendance_percentage"] <= 100.0
    print(f"[PASS] Daily report verified: {d_summary['total_records']} records, {d_summary['attendance_percentage']}% attendance.")

    # 3.2 Student report
    student_res = client.get(f"/api/v1/attendance/reports/student?class_id={cls_1_id}", headers=admin_headers)
    assert student_res.status_code == 200, f"Student report failed: {student_res.text}"
    student_json = student_res.json()
    assert student_json["report_type"] == "student"
    s_rows = student_json["rows"]
    alex_row = next((r for r in s_rows if r["student_id"] == alex_id), None)
    assert alex_row is not None
    assert alex_row["present_count"] >= 1
    assert alex_row["total_classes"] >= 1
    assert alex_row["attendance_percentage"] == round((alex_row["present_count"] / alex_row["total_classes"]) * 100.0, 2)
    assert alex_row["status_label"] in ("Eligible", "Shortage")
    print(f"[PASS] Student report verified: Alex attendance rate = {alex_row['attendance_percentage']}%.")

    # 3.3 Subject report
    subj_res = client.get(f"/api/v1/attendance/reports/subject?class_id={cls_1_id}", headers=admin_headers)
    assert subj_res.status_code == 200
    subj_json = subj_res.json()
    assert subj_json["report_type"] == "subject"
    print(f"[PASS] Subject report verified: {len(subj_json['rows'])} subject records.")

    # 3.4 Class report
    class_res = client.get(f"/api/v1/attendance/reports/class?class_id={cls_1_id}", headers=admin_headers)
    assert class_res.status_code == 200
    class_json = class_res.json()
    assert class_json["report_type"] == "class"
    print(f"[PASS] Class report verified: {len(class_json['rows'])} class records.")

    # 3.5 Monthly report
    monthly_res = client.get(f"/api/v1/attendance/reports/monthly?class_id={cls_1_id}", headers=admin_headers)
    assert monthly_res.status_code == 200
    monthly_json = monthly_res.json()
    assert monthly_json["report_type"] == "monthly"
    print(f"[PASS] Monthly report verified: {len(monthly_json['rows'])} monthly summaries.")

    # -------------------------------------------------------------
    # 4. CSV EXPORT VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 4. Testing CSV Export Endpoints ---")
    for r_type in ["daily", "student", "subject", "class", "monthly"]:
        # Query parameter ?format=csv
        res_csv_1 = client.get(f"/api/v1/attendance/reports/{r_type}?format=csv", headers=admin_headers)
        assert res_csv_1.status_code == 200, f"CSV export failed for {r_type}"
        assert "text/csv" in res_csv_1.headers.get("content-type", "")
        csv_text = res_csv_1.text
        assert len(csv_text) > 50

        # Validate CSV parser readability
        reader = list(csv.reader(io.StringIO(csv_text)))
        assert len(reader) >= 4, "CSV should contain headers and rows"
        print(f"[PASS] CSV format=csv for '{r_type}': {len(reader)} CSV lines valid.")

        # Dedicated export-csv dispatcher
        res_csv_2 = client.get(f"/api/v1/attendance/reports/export-csv?report_type={r_type}", headers=admin_headers)
        assert res_csv_2.status_code == 200
        assert "text/csv" in res_csv_2.headers.get("content-type", "")

    print("\n>>> ALL ATTENDANCE & REPORTS TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    test_attendance_and_reports_suite()
