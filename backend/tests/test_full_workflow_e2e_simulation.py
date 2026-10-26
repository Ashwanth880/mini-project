"""
Complete End-to-End Simulation and Verification of the One-Click Attendance System.

This script executes the exact sequence demanded by the institutional workflow:
ADMIN
↓ Create class
↓ Create subject
↓ Create class teacher
↓ Create subject teacher
↓ Assign teachers
↓ Create students
CLASS TEACHER
↓ Upload student images
↓ Generate face embeddings
↓ Verify enrollment
SUBJECT TEACHER
↓ Login
↓ Select class
↓ Select subject
↓ Select period
↓ Capture classroom image
↓ Detect faces
↓ Recognize students
↓ Generate attendance preview
↓ Confirm attendance
DATABASE
↓ Save attendance
REPORT
↓ Display attendance percentage

Validates every single stage for errors, ensures database integrity,
and verifies zero early-save leaks and 100% accurate reporting metrics.
"""

import io
import json
import sys
import uuid
from datetime import date
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.attendance import Attendance, AttendanceStatus
from app.models.academic import Class, Subject, ClassSubject
from app.models.student import Student
from app.models.user import User

client = TestClient(app)
samples_dir = backend_dir.parent / "data" / "test_samples"


def load_sample_bytes(filename: str) -> bytes:
    sample_path = samples_dir / filename
    assert sample_path.exists(), f"Sample image file {sample_path} does not exist."
    with open(sample_path, "rb") as f:
        return f.read()


def test_complete_institution_workflow_simulation():
    print("=" * 80)
    print("STARTING FULL END-TO-END ONE-CLICK ATTENDANCE WORKFLOW SIMULATION")
    print("=" * 80)

    unique_id = uuid.uuid4().hex[:6]
    today_str = date.today().isoformat()
    test_period = 2

    # =========================================================================
    # STAGE 1: ADMIN WORKFLOW
    # =========================================================================
    print("\n[STAGE 1: ADMIN] Authenticating Administrator...")
    login_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_admin.status_code == 200, f"Admin login failed: {login_admin.text}"
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  -> Admin authenticated successfully.")

    # 1.1 Create Class
    print("\n[STAGE 1.1: ADMIN] Creating Academic Class...")
    class_payload = {
        "name": f"B.Tech CSE - 3rd Year - Sec A_{unique_id}",
        "department": f"CSE_{unique_id}",
        "year": 3,
        "section": "A",
        "class_teacher_id": None,
    }
    res_class = client.post("/api/v1/admin/classes", json=class_payload, headers=admin_headers)
    assert res_class.status_code == 201, f"Create class failed: {res_class.text}"
    class_data = res_class.json()
    class_id = class_data["id"]
    print(f"  -> Created Class ID #{class_id}: '{class_data['name']}'")

    # 1.2 Create Subject
    print("\n[STAGE 1.2: ADMIN] Creating Academic Subject...")
    subject_code = f"CS{unique_id[:4].upper()}"
    subject_payload = {
        "code": subject_code,
        "name": f"Artificial Intelligence & ML {unique_id}",
        "department": f"CSE_{unique_id}",
    }
    res_subj = client.post("/api/v1/admin/subjects", json=subject_payload, headers=admin_headers)
    assert res_subj.status_code == 201, f"Create subject failed: {res_subj.text}"
    subject_data = res_subj.json()
    subject_id = subject_data["id"]
    print(f"  -> Created Subject ID #{subject_id}: '{subject_data['name']}' ({subject_data['code']})")

    # 1.3 Create Class Teacher
    print("\n[STAGE 1.3: ADMIN] Creating Class Teacher...")
    ct_username = f"prof_verma_{unique_id}"
    ct_payload = {
        "username": ct_username,
        "full_name": "Prof. R. K. Verma",
        "email": f"verma_{unique_id}@college.edu",
        "phone": "+91-9876501234",
        "department": f"CSE_{unique_id}",
        "role": "CLASS_TEACHER",
        "password": "Password@123",
    }
    res_ct = client.post("/api/v1/admin/teachers", json=ct_payload, headers=admin_headers)
    assert res_ct.status_code == 201, f"Create class teacher failed: {res_ct.text}"
    ct_data = res_ct.json()
    class_teacher_id = ct_data["id"]
    print(f"  -> Created Class Teacher ID #{class_teacher_id}: {ct_data['full_name']} ({ct_data['username']})")

    # 1.4 Create Subject Teacher
    print("\n[STAGE 1.4: ADMIN] Creating Subject Teacher...")
    st_username = f"prof_roy_{unique_id}"
    st_payload = {
        "username": st_username,
        "full_name": "Dr. Ananya Roy",
        "email": f"ananya_{unique_id}@college.edu",
        "phone": "+91-9876505678",
        "department": f"CSE_{unique_id}",
        "role": "SUBJECT_TEACHER",
        "password": "Password@123",
    }
    res_st = client.post("/api/v1/admin/teachers", json=st_payload, headers=admin_headers)
    assert res_st.status_code == 201, f"Create subject teacher failed: {res_st.text}"
    st_data = res_st.json()
    subject_teacher_id = st_data["id"]
    print(f"  -> Created Subject Teacher ID #{subject_teacher_id}: {st_data['full_name']} ({st_data['username']})")

    # 1.5 Assign Teachers
    print("\n[STAGE 1.5: ADMIN] Assigning Teachers...")
    # Assign Class Teacher to Class
    res_assign_ct = client.put(
        f"/api/v1/admin/classes/{class_id}/assign-teacher",
        json={"class_teacher_id": class_teacher_id},
        headers=admin_headers,
    )
    assert res_assign_ct.status_code == 200, f"Assign class teacher failed: {res_assign_ct.text}"
    print(f"  -> Assigned '{ct_data['full_name']}' as Class Teacher for Class ID #{class_id}.")

    # Assign Subject Teacher to Class & Subject
    assign_payload = {
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": subject_teacher_id,
    }
    res_assign_st = client.post("/api/v1/admin/assignments", json=assign_payload, headers=admin_headers)
    assert res_assign_st.status_code == 201, f"Assign subject teacher failed: {res_assign_st.text}"
    print(f"  -> Assigned '{st_data['full_name']}' to teach '{subject_data['name']}' to Class ID #{class_id}.")

    # 1.6 Create Students
    print("\n[STAGE 1.6: ADMIN] Creating Students...")
    # Student 1: Alex Mercer (Present in classroom photo)
    s1_payload = {
        "class_id": class_id,
        "roll_number": f"CS301_{unique_id}",
        "register_number": f"REG-CS301_{unique_id}",
        "full_name": "Alex Mercer",
        "department": f"CSE_{unique_id}",
        "year": 3,
        "section": "A",
        "email": f"alex_{unique_id}@college.edu",
        "phone": "+91-9123450001",
    }
    res_s1 = client.post("/api/v1/admin/students", json=s1_payload, headers=admin_headers)
    assert res_s1.status_code == 201, f"Create Student 1 failed: {res_s1.text}"
    s1 = res_s1.json()
    student_1_id = s1["id"]
    print(f"  -> Created Student 1: '{s1['full_name']}' (ID #{student_1_id}, Roll: {s1['roll_number']})")

    # Student 2: Priya Sharma (Present in classroom photo)
    s2_payload = {
        "class_id": class_id,
        "roll_number": f"CS302_{unique_id}",
        "register_number": f"REG-CS302_{unique_id}",
        "full_name": "Priya Sharma",
        "department": f"CSE_{unique_id}",
        "year": 3,
        "section": "A",
        "email": f"priya_{unique_id}@college.edu",
        "phone": "+91-9123450002",
    }
    res_s2 = client.post("/api/v1/admin/students", json=s2_payload, headers=admin_headers)
    assert res_s2.status_code == 201, f"Create Student 2 failed: {res_s2.text}"
    s2 = res_s2.json()
    student_2_id = s2["id"]
    print(f"  -> Created Student 2: '{s2['full_name']}' (ID #{student_2_id}, Roll: {s2['roll_number']})")

    # Student 3: Rahul Verma (Absent from classroom photo)
    s3_payload = {
        "class_id": class_id,
        "roll_number": f"CS303_{unique_id}",
        "register_number": f"REG-CS303_{unique_id}",
        "full_name": "Rahul Verma",
        "department": f"CSE_{unique_id}",
        "year": 3,
        "section": "A",
        "email": f"rahul_{unique_id}@college.edu",
        "phone": "+91-9123450003",
    }
    res_s3 = client.post("/api/v1/admin/students", json=s3_payload, headers=admin_headers)
    assert res_s3.status_code == 201, f"Create Student 3 failed: {res_s3.text}"
    s3 = res_s3.json()
    student_3_id = s3["id"]
    print(f"  -> Created Student 3: '{s3['full_name']}' (ID #{student_3_id}, Roll: {s3['roll_number']})")

    # =========================================================================
    # STAGE 2: CLASS TEACHER WORKFLOW
    # =========================================================================
    print("\n[STAGE 2: CLASS TEACHER] Authenticating Class Teacher...")
    login_ct = client.post("/auth/login", json={"username": ct_username, "password": "Password@123"})
    assert login_ct.status_code == 200, f"Class teacher login failed: {login_ct.text}"
    ct_token = login_ct.json()["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}
    print(f"  -> Authenticated as Class Teacher: {login_ct.json()['user']['full_name']}")

    # 2.1 View Assigned Class
    print("\n[STAGE 2.1: CLASS TEACHER] Viewing Assigned Class Roster...")
    res_my_class = client.get("/api/v1/teachers/class-teacher/my-class", headers=ct_headers)
    assert res_my_class.status_code == 200, f"Get my-class failed: {res_my_class.text}"
    my_class_data = res_my_class.json()
    assert my_class_data["id"] == class_id
    assert my_class_data["total_students"] == 3
    print(f"  -> Verified Class: '{my_class_data['name']}' with 3 enrolled students.")

    # 2.2 Upload Student Images & Generate Face Embeddings
    print("\n[STAGE 2.2: CLASS TEACHER] Uploading Student Face Images & Extracting 128D Embeddings...")
    # Upload Alex Mercer's portrait
    alex_photo_bytes = load_sample_bytes("student_alex.jpg")
    res_up1 = client.post(
        f"/api/v1/teachers/class-teacher/students/{student_1_id}/upload-face",
        files={"file": ("student_alex.jpg", alex_photo_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_up1.status_code == 200, f"Upload face Alex failed: {res_up1.text}"
    enr1 = res_up1.json()
    assert enr1["face_enrolled"] is True
    assert enr1["embedding_dimension"] == 128
    print(f"  -> Student 1 (Alex Mercer): 128D face embedding generated! Path: {enr1['face_image_path']}")

    # Upload Priya Sharma's portrait
    priya_photo_bytes = load_sample_bytes("student_priya.jpg")
    res_up2 = client.post(
        f"/api/v1/teachers/class-teacher/students/{student_2_id}/upload-face",
        files={"file": ("student_priya.jpg", priya_photo_bytes, "image/jpeg")},
        headers=ct_headers,
    )
    assert res_up2.status_code == 200, f"Upload face Priya failed: {res_up2.text}"
    enr2 = res_up2.json()
    assert enr2["face_enrolled"] is True
    assert enr2["embedding_dimension"] == 128
    print(f"  -> Student 2 (Priya Sharma): 128D face embedding generated! Path: {enr2['face_image_path']}")

    # 2.3 Verify Enrollment
    print("\n[STAGE 2.3: CLASS TEACHER] Verifying Face Enrollment Status...")
    res_face1 = client.get(f"/api/v1/teachers/class-teacher/students/{student_1_id}/face", headers=ct_headers)
    assert res_face1.status_code == 200
    assert res_face1.json()["face_enrolled"] is True

    res_face2 = client.get(f"/api/v1/teachers/class-teacher/students/{student_2_id}/face", headers=ct_headers)
    assert res_face2.status_code == 200
    assert res_face2.json()["face_enrolled"] is True

    res_face3 = client.get(f"/api/v1/teachers/class-teacher/students/{student_3_id}/face", headers=ct_headers)
    assert res_face3.status_code == 200
    assert res_face3.json()["face_enrolled"] is False

    res_summary = client.get("/api/v1/teachers/class-teacher/attendance-summary", headers=ct_headers)
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert summary_data["total_students"] == 3
    assert summary_data["face_enrolled_count"] == 2
    print(f"  -> Enrollment verified: 2 of 3 students have enrolled face embeddings.")

    # =========================================================================
    # STAGE 3: SUBJECT TEACHER WORKFLOW
    # =========================================================================
    print("\n[STAGE 3: SUBJECT TEACHER] Authenticating Subject Teacher...")
    login_st = client.post("/auth/login", json={"username": st_username, "password": "Password@123"})
    assert login_st.status_code == 200, f"Subject teacher login failed: {login_st.text}"
    st_token = login_st.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}
    st_user_id = login_st.json()["user"]["id"]
    print(f"  -> Authenticated as Subject Teacher: {login_st.json()['user']['full_name']}")

    # 3.1 Select Class & Subject
    print("\n[STAGE 3.1: SUBJECT TEACHER] Selecting Assigned Class & Subject...")
    res_st_classes = client.get("/api/v1/teachers/subject-teacher/classes", headers=st_headers)
    assert res_st_classes.status_code == 200, f"Get assigned classes failed: {res_st_classes.text}"
    st_classes_data = res_st_classes.json()
    assigned_class_ids = [c["id"] for c in st_classes_data["assigned_classes"]]
    assert class_id in assigned_class_ids, f"Class #{class_id} not found in assigned classes: {assigned_class_ids}"

    assigned_subject_ids = [s["subject_id"] for s in st_classes_data["assigned_subjects"] if s["class_id"] == class_id]
    assert subject_id in assigned_subject_ids, f"Subject #{subject_id} not assigned for class #{class_id}"
    print(f"  -> Verified Class ID #{class_id} and Subject ID #{subject_id} are actively assigned to teacher.")

    # 3.2 Capture Classroom Image, Detect Faces & Generate Preview
    print("\n[STAGE 3.2: SUBJECT TEACHER] Analyzing Classroom Group Photograph...")
    classroom_photo_bytes = load_sample_bytes("classroom_alex_priya.jpg")

    # Verify Database count before analysis: MUST NOT INCREASE!
    db = SessionLocal()
    count_before = db.query(Attendance).count()
    db.close()

    res_analyze = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=st_headers,
        data={
            "class_id": str(class_id),
            "subject_id": str(subject_id),
            "period": str(test_period),
            "date_str": today_str,
            "threshold": "0.45",
        },
        files={"photo": ("classroom.jpg", classroom_photo_bytes, "image/jpeg")},
    )
    assert res_analyze.status_code == 200, f"Classroom photo analysis failed: {res_analyze.text}"
    analysis = res_analyze.json()

    # CHECK NO EARLY SAVE
    db = SessionLocal()
    count_after = db.query(Attendance).count()
    db.close()
    assert count_after == count_before, (
        f"VIOLATION: Analysis immediately saved records! Count before: {count_before}, count after: {count_after}"
    )
    print("  -> Zero early-save verified: database attendance record count remained strictly unchanged.")

    # Validate analysis contents
    assert analysis["total_faces_detected"] >= 2, f"Expected >=2 faces detected, got {analysis['total_faces_detected']}"
    assert analysis["recognized_count"] == 2, f"Expected 2 recognized students, got {analysis['recognized_count']}"
    assert analysis["present_count"] == 2
    assert analysis["absent_count"] == 1
    assert analysis["total_students_in_class"] == 3
    assert analysis["annotated_image_url"] is not None

    previews = {p["student_id"]: p for p in analysis["preview_records"]}
    assert student_1_id in previews
    assert previews[student_1_id]["status"] == "PRESENT"
    assert previews[student_1_id]["confidence"] > 60.0
    print(f"  -> Alex Mercer detected and recognized: PRESENT (Confidence: {previews[student_1_id]['confidence']}%)")

    assert student_2_id in previews
    assert previews[student_2_id]["status"] == "PRESENT"
    assert previews[student_2_id]["confidence"] > 60.0
    print(f"  -> Priya Sharma detected and recognized: PRESENT (Confidence: {previews[student_2_id]['confidence']}%)")

    assert student_3_id in previews
    assert previews[student_3_id]["status"] == "ABSENT"
    print(f"  -> Rahul Verma not present in photo: ABSENT")

    # 3.3 Confirm Attendance
    print("\n[STAGE 3.3: SUBJECT TEACHER] Confirming Attendance and Committing to Ledger...")
    confirmed_records = []
    for item in analysis["preview_records"]:
        confirmed_records.append({
            "student_id": item["student_id"],
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": st_user_id,
            "date": today_str,
            "period": test_period,
            "status": item["status"],
            "confidence": item["confidence"],
            "attendance_image_id": analysis["attendance_image_id"],
            "bounding_box": json.dumps(item["bounding_box"]) if item["bounding_box"] else None,
            "is_manual": False,
        })

    res_confirm = client.post(
        "/api/v1/attendance/confirm",
        json={"confirmed_records": confirmed_records},
        headers=st_headers,
    )
    assert res_confirm.status_code == 200, f"Attendance confirmation failed: {res_confirm.text}"
    saved_confirm = res_confirm.json()
    assert len(saved_confirm) == 3
    print(f"  -> Successfully confirmed and persisted {len(saved_confirm)} attendance ledger records!")

    # =========================================================================
    # STAGE 4: DATABASE RECORD VERIFICATION
    # =========================================================================
    print("\n[STAGE 4: DATABASE] Direct Ledger Record Inspection...")
    db = SessionLocal()
    db_records = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == class_id,
            Attendance.subject_id == subject_id,
            Attendance.date == date.today(),
            Attendance.period == test_period,
        )
        .all()
    )
    assert len(db_records) == 3, f"Expected 3 records in DB, found {len(db_records)}"
    status_map = {r.student_id: r.status for r in db_records}
    assert status_map[student_1_id] == AttendanceStatus.PRESENT
    assert status_map[student_2_id] == AttendanceStatus.PRESENT
    assert status_map[student_3_id] == AttendanceStatus.ABSENT
    db.close()
    print("  -> Database inspection confirmed: Alex=PRESENT, Priya=PRESENT, Rahul=ABSENT.")

    # =========================================================================
    # STAGE 5: REPORT & ANALYTICS VERIFICATION
    # =========================================================================
    print("\n[STAGE 5: REPORT] Attendance Percentages & Analytics Verification...")
    # 5.1 Student Attendance Report
    res_st_rep = client.get(
        f"/api/v1/attendance/reports/student?class_id={class_id}&subject_id={subject_id}",
        headers=admin_headers,
    )
    assert res_st_rep.status_code == 200, f"Student report failed: {res_st_rep.text}"
    report_data = res_st_rep.json()
    assert report_data["report_type"] == "student"
    assert "rows" in report_data
    assert len(report_data["rows"]) == 3
    rep_students = {r["student_id"]: r for r in report_data["rows"]}

    alex_rep = rep_students[student_1_id]
    assert alex_rep["attendance_percentage"] == 100.0
    print(f"  -> Alex Mercer Attendance Percentage: {alex_rep['attendance_percentage']}% (1/1 sessions present)")

    priya_rep = rep_students[student_2_id]
    assert priya_rep["attendance_percentage"] == 100.0
    print(f"  -> Priya Sharma Attendance Percentage: {priya_rep['attendance_percentage']}% (1/1 sessions present)")

    rahul_rep = rep_students[student_3_id]
    assert rahul_rep["attendance_percentage"] == 0.0
    print(f"  -> Rahul Verma Attendance Percentage: {rahul_rep['attendance_percentage']}% (0/1 sessions present)")

    # 5.2 Daily Report
    res_daily = client.get(
        f"/api/v1/attendance/reports/daily?class_id={class_id}&subject_id={subject_id}",
        headers=admin_headers,
    )
    assert res_daily.status_code == 200, f"Daily report failed: {res_daily.text}"
    daily_data = res_daily.json()
    assert daily_data["report_type"] == "daily"
    d_summary = daily_data["summary"]
    assert d_summary["present_count"] == 2
    assert d_summary["absent_count"] == 1
    assert d_summary["attendance_percentage"] == 66.67 or d_summary["attendance_percentage"] == 66.7
    print(f"  -> Daily Session Overall Percentage: {d_summary['attendance_percentage']}% (2 Present, 1 Absent)")

    # 5.3 CSV Export
    res_csv = client.get(
        f"/api/v1/attendance/reports/daily?class_id={class_id}&subject_id={subject_id}&format=csv",
        headers=admin_headers,
    )
    assert res_csv.status_code == 200, f"CSV export failed: {res_csv.text}"
    assert "text/csv" in res_csv.headers.get("content-type", "")
    assert len(res_csv.text) > 20
    print("  -> CSV Export verified: Content-Type text/csv, non-empty content returned.")

    print("\n" + "=" * 80)
    print("ALL 5 STAGES OF THE END-TO-END WORKFLOW SIMULATION PASSED CLEANLY!")
    print("=" * 80)


if __name__ == "__main__":
    test_complete_institution_workflow_simulation()
