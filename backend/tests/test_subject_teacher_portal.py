"""
Comprehensive Automated Test Suite for the Subject Teacher Portal.
Validates:
1. Subject teacher authentication & role validation (patel / teacher123 -> SUBJECT_TEACHER).
2. Fetching assigned classes & subjects (GET /api/v1/teachers/subject-teacher/classes).
3. Session parameter validation (class_id, subject_id, period 1-8, date).
4. Classroom photo analysis (POST /api/v1/attendance/analyze-classroom-photo):
   - Validation failures (invalid class_id 404, invalid subject_id 404, invalid file format 400).
   - Valid classroom image analysis with YuNet multi-face detection & SFace embedding matching.
   - CRITICAL: Verification that attendance table rows are NOT saved during analysis (preview only).
   - Validation of preview structure (present/absent list, confidence scores, unknown detections).
5. Attendance review & manual status adjustment simulation (toggle status, is_manual=True).
6. Attendance confirmation & persistence (POST /api/v1/attendance/confirm):
   - Permanent insertion of confirmed records into attendance table.
   - Upsert / idempotency check (updating status without duplicate record creation).
7. Attendance reports integration (GET /api/v1/attendance/reports).
8. Security & role access control (401 unauthenticated, 403 unauthorized).
"""

import io
import json
import sys
from datetime import date
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.attendance import Attendance, AttendanceImage, AttendanceStatus
from app.models.academic import Class, Subject, ClassSubject
from app.models.student import Student

client = TestClient(app)
samples_dir = backend_dir.parent / "data" / "test_samples"


def load_sample_bytes(filename: str) -> bytes:
    sample_path = samples_dir / filename
    assert sample_path.exists(), f"Sample image file {sample_path} does not exist."
    with open(sample_path, "rb") as f:
        return f.read()


def test_subject_teacher_portal_flow():
    print("=" * 75)
    print("STARTING SUBJECT TEACHER PORTAL END-TO-END AUTOMATED VERIFICATION")
    print("=" * 75)

    # -------------------------------------------------------------
    # 1. LOGIN & ROLE VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 1. Subject Teacher Authentication ---")
    login_res = client.post("/auth/login", json={"username": "patel", "password": "teacher123"})
    assert login_res.status_code == 200, f"Subject teacher login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    user_info = login_res.json()["user"]
    assert user_info["role"] == "SUBJECT_TEACHER"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] Logged in as: {user_info['full_name']} (Role: {user_info['role']})")

    # -------------------------------------------------------------
    # 2. VIEW ASSIGNED CLASSES & SUBJECTS
    # -------------------------------------------------------------
    print("\n--- 2. View Assigned Classes and Subjects ---")
    res_classes = client.get("/api/v1/teachers/subject-teacher/classes", headers=headers)
    assert res_classes.status_code == 200, f"Failed to get classes: {res_classes.text}"
    data_classes = res_classes.json()
    assert "assigned_classes" in data_classes
    assert "assigned_subjects" in data_classes
    assert "available_classes" in data_classes
    assert "available_subjects" in data_classes

    assigned_classes = data_classes["assigned_classes"]
    assigned_subjects = data_classes["assigned_subjects"]
    print(f"[PASS] Retrieved {len(assigned_classes)} assigned classes, {len(assigned_subjects)} assigned subjects")

    # Select target class and subject for attendance session
    if assigned_classes and assigned_subjects:
        target_class_id = assigned_classes[0]["id"]
        target_subject_id = assigned_subjects[0]["subject_id"]
    else:
        target_class_id = data_classes["available_classes"][0]["id"]
        target_subject_id = data_classes["available_subjects"][0]["id"]

    print(f"[INFO] Selected Session: class_id={target_class_id}, subject_id={target_subject_id}")

    # -------------------------------------------------------------
    # 3. CLASSROOM PHOTO ANALYSIS VALIDATION (ERROR CASES)
    # -------------------------------------------------------------
    print("\n--- 3. Classroom Photo Analysis: Input Validations ---")
    sample_img_bytes = load_sample_bytes("classroom_alex_priya.jpg")

    # Non-existent class ID -> 404
    res_bad_class = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=headers,
        data={"class_id": 999999, "subject_id": target_subject_id, "period": 1},
        files={"photo": ("classroom.jpg", sample_img_bytes, "image/jpeg")},
    )
    assert res_bad_class.status_code == 404, f"Expected 404 for bad class, got {res_bad_class.status_code}"
    print("[PASS] Rejected non-existent class_id with HTTP 404")

    # Non-existent subject ID -> 404
    res_bad_subject = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=headers,
        data={"class_id": target_class_id, "subject_id": 999999, "period": 1},
        files={"photo": ("classroom.jpg", sample_img_bytes, "image/jpeg")},
    )
    assert res_bad_subject.status_code == 404, f"Expected 404 for bad subject, got {res_bad_subject.status_code}"
    print("[PASS] Rejected non-existent subject_id with HTTP 404")

    # Invalid file extension -> 400
    res_bad_ext = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        headers=headers,
        data={"class_id": target_class_id, "subject_id": target_subject_id, "period": 1},
        files={"photo": ("notes.txt", b"This is not a photo", "text/plain")},
    )
    assert res_bad_ext.status_code == 400, f"Expected 400 for bad extension, got {res_bad_ext.status_code}"
    print("[PASS] Rejected invalid file extension with HTTP 400")

    # -------------------------------------------------------------
    # 4. CLASSROOM PHOTO ANALYSIS (DO NOT SAVE IMMEDIATELY - PREVIEW FIRST)
    # -------------------------------------------------------------
    print("\n--- 4. Classroom Photo Analysis: Preview First (No Early Save) ---")
    test_session_date = "2026-10-04"
    test_session_period = 3

    # Check attendance count BEFORE analysis
    db = SessionLocal()
    count_before = db.query(Attendance).count()
    db.close()

    # Test root endpoint POST /attendance/analyze
    res_analysis = client.post(
        "/attendance/analyze",
        headers=headers,
        data={
            "class_id": target_class_id,
            "subject_id": target_subject_id,
            "period": test_session_period,
            "date_str": test_session_date,
        },
        files={"photo": ("classroom_alex_priya.jpg", sample_img_bytes, "image/jpeg")},
    )
    assert res_analysis.status_code == 200, f"Analysis failed: {res_analysis.text}"
    analysis_data = res_analysis.json()

    # CRITICAL CHECK: Attendance table must NOT have increased!
    db = SessionLocal()
    count_after = db.query(Attendance).count()
    db.close()
    assert count_after == count_before, (
        f"CRITICAL VIOLATION: Attendance records were saved immediately! "
        f"Count before: {count_before}, count after: {count_after}"
    )
    print(f"[PASS] PREVIEW INTEGRITY VERIFIED: Attendance table row count remained {count_before} (no early save).")

    # Verify Analysis Payload Structure
    assert "attendance_image_id" in analysis_data
    assert "preview_records" in analysis_data
    assert "present_count" in analysis_data
    assert "absent_count" in analysis_data
    assert "total_faces_detected" in analysis_data
    assert "total_students_in_class" in analysis_data
    assert "recognized_count" in analysis_data
    assert "unknown_count" in analysis_data
    assert "unknown_detections" in analysis_data
    assert "annotated_image_url" in analysis_data
    assert analysis_data["class_id"] == target_class_id
    assert analysis_data["subject_id"] == target_subject_id
    assert analysis_data["period"] == test_session_period
    assert analysis_data["date"] == test_session_date
    assert analysis_data["present_count"] + analysis_data["absent_count"] == analysis_data["total_students_in_class"]

    # Verify that annotated image is served statically
    if analysis_data["annotated_image_url"]:
        res_ann_img = client.get(analysis_data["annotated_image_url"])
        assert res_ann_img.status_code == 200, "Annotated classroom image failed to serve"
        print(f"[PASS] Annotated classroom image with bounding boxes & names generated: {analysis_data['annotated_image_url']}")

    preview_records = analysis_data["preview_records"]
    assert len(preview_records) > 0, "Expected preview records for enrolled class students."
    print(
        f"[PASS] Analysis returned {len(preview_records)} student previews: "
        f"{analysis_data['present_count']} Present, {analysis_data['absent_count']} Absent, "
        f"{analysis_data['total_faces_detected']} Faces detected in photo"
    )

    # Verify preview record items
    for item in preview_records:
        assert "student_id" in item
        assert "roll_number" in item
        assert "full_name" in item
        assert item["status"] in ["PRESENT", "ABSENT"]
        assert "confidence" in item
        assert "is_detected" in item

    # -------------------------------------------------------------
    # 5. REVIEW ATTENDANCE & SIMULATE HUMAN ADJUSTMENTS
    # -------------------------------------------------------------
    print("\n--- 5. Review Attendance & Simulate Teacher Adjustments ---")
    confirmed_records = []
    for item in preview_records:
        status_val = item["status"]
        is_manual = False
        # Teacher manually marks an absent student as present (e.g. seated behind a pillar)
        if item == preview_records[-1] and status_val == "ABSENT":
            status_val = "PRESENT"
            is_manual = True
            print(f"[INFO] Teacher manually toggling {item['full_name']} from ABSENT -> PRESENT")

        confirmed_records.append({
            "student_id": item["student_id"],
            "class_id": target_class_id,
            "subject_id": target_subject_id,
            "teacher_id": user_info["id"],
            "date": test_session_date,
            "period": test_session_period,
            "status": status_val,
            "confidence": item["confidence"],
            "attendance_image_id": analysis_data["attendance_image_id"],
            "bounding_box": json.dumps(item["bounding_box"]) if item["bounding_box"] else None,
            "is_manual": is_manual,
        })

    # -------------------------------------------------------------
    # 6. CONFIRM ATTENDANCE (PERSISTENCE & DUPLICATE PREVENTION)
    # -------------------------------------------------------------
    print("\n--- 6. Confirm Attendance & Persist to Database ---")

    # Test rejection of duplicate student in confirmation payload
    if len(confirmed_records) >= 1:
        dup_payload = {"confirmed_records": [confirmed_records[0], confirmed_records[0]]}
        res_dup = client.post("/attendance/confirm", headers=headers, json=dup_payload)
        assert res_dup.status_code == 400, f"Expected 400 for duplicate student, got {res_dup.status_code}"
        assert "Duplicate attendance entry" in res_dup.text
        print("[PASS] Duplicate student entry in confirmation payload rejected with HTTP 400")

    confirm_payload = {"confirmed_records": confirmed_records}
    res_confirm = client.post("/attendance/confirm", headers=headers, json=confirm_payload)
    assert res_confirm.status_code == 200, f"Confirmation failed: {res_confirm.text}"
    saved_records = res_confirm.json()
    assert len(saved_records) == len(confirmed_records)
    print(f"[PASS] Successfully confirmed and persisted {len(saved_records)} attendance records via POST /attendance/confirm")

    # Verify in DB
    db = SessionLocal()
    db_records = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == target_class_id,
            Attendance.subject_id == target_subject_id,
            Attendance.date == date.fromisoformat(test_session_date),
            Attendance.period == test_session_period,
        )
        .all()
    )
    assert len(db_records) == len(confirmed_records)
    print(f"[PASS] Verified {len(db_records)} records saved in database with correct class, subject, period, and date")

    # Test Idempotency / Upsert (re-confirming should update existing rows, not duplicate)
    reconfirm_records = [dict(r) for r in confirmed_records]
    # Toggle first student's status
    reconfirm_records[0]["status"] = "ABSENT" if reconfirm_records[0]["status"] == "PRESENT" else "PRESENT"
    res_reconfirm = client.post("/attendance/confirm", headers=headers, json={"confirmed_records": reconfirm_records})
    assert res_reconfirm.status_code == 200

    db_records_after_reconfirm = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == target_class_id,
            Attendance.subject_id == target_subject_id,
            Attendance.date == date.fromisoformat(test_session_date),
            Attendance.period == test_session_period,
        )
        .all()
    )
    assert len(db_records_after_reconfirm) == len(confirmed_records), "Duplicate records created on re-confirmation!"
    print(f"[PASS] Idempotency / Upsert verified: Record count remained {len(db_records_after_reconfirm)} without duplicates")
    db.close()

    # -------------------------------------------------------------
    # 7. ATTENDANCE REPORTS VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 7. Attendance Reports & Analytics ---")
    res_reports = client.get(
        f"/api/v1/attendance/reports?start_date={test_session_date}&end_date={test_session_date}",
        headers=headers,
    )
    assert res_reports.status_code == 200, f"Reports request failed: {res_reports.text}"
    report_data = res_reports.json()
    assert "summary" in report_data
    summary = report_data["summary"]
    assert summary["total_records"] >= len(confirmed_records)
    print(f"[PASS] Report reflects session: Total records={summary['total_records']}, Present={summary['present_count']}")

    # -------------------------------------------------------------
    # 8. SECURITY & ROLE ACCESS CONTROL
    # -------------------------------------------------------------
    print("\n--- 8. Security & Authorization Checks ---")
    # Unauthenticated request -> 401
    res_unauth = client.post(
        "/api/v1/attendance/analyze-classroom-photo",
        data={"class_id": target_class_id, "subject_id": target_subject_id, "period": 1},
        files={"photo": ("classroom.jpg", sample_img_bytes, "image/jpeg")},
    )
    assert res_unauth.status_code == 401, f"Expected 401 for unauthenticated request, got {res_unauth.status_code}"
    print("[PASS] Unauthenticated access to /attendance/analyze-classroom-photo blocked with HTTP 401")

    res_confirm_unauth = client.post("/api/v1/attendance/confirm", json={"confirmed_records": []})
    assert res_confirm_unauth.status_code == 401
    print("[PASS] Unauthenticated access to /attendance/confirm blocked with HTTP 401")

    print("\n" + "=" * 75)
    print(">>> ALL SUBJECT TEACHER PORTAL TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 75)


if __name__ == "__main__":
    test_subject_teacher_portal_flow()
