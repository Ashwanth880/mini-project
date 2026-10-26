"""
Live HTTP Verification Script.
Connects directly to the live running FastAPI server on http://127.0.0.1:8000
and runs the complete workflow over actual TCP sockets.
"""

import sys
import uuid
import json
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
samples_dir = Path(__file__).resolve().parent.parent.parent / "data" / "test_samples"


def load_file(name: str) -> bytes:
    p = samples_dir / name
    with open(p, "rb") as f:
        return f.read()


def make_request(path: str, method="GET", data=None, headers=None, is_json=True, raw_body=None, content_type=None):
    url = f"{BASE_URL}{path}"
    req_headers = headers or {}
    body = None

    if raw_body is not None:
        body = raw_body
        if content_type:
            req_headers["Content-Type"] = content_type
    elif data is not None:
        if is_json:
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read()
            c_type = resp.headers.get("Content-Type", "")
            if "application/json" in c_type:
                return status, json.loads(content.decode("utf-8"))
            return status, content
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_content)
            return e.code, err_json
        except Exception:
            return e.code, err_content


def test_live_http_end_to_end():
    print("=" * 75)
    print("STARTING LIVE HTTP (TCP SOCKET) END-TO-END WORKFLOW VERIFICATION")
    print(f"Target: {BASE_URL}")
    print("=" * 75)

    uid = uuid.uuid4().hex[:6]

    # 1. Health check
    status, health = make_request("/health")
    assert status == 200, f"Health check failed: {health}"
    print(f"[PASS] Server Health: {health['status']}")

    # 2. Admin Login
    status, admin_auth = make_request("/auth/login", method="POST", data={"username": "admin", "password": "admin123"})
    assert status == 200, f"Admin login failed: {admin_auth}"
    admin_token = admin_auth["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] Admin Logged In over live HTTP.")

    # 3. Create Class
    class_payload = {
        "name": f"ECE 4th Year Sec A_{uid}",
        "department": f"ECE_{uid}",
        "year": 4,
        "section": "A",
        "class_teacher_id": None,
    }
    status, cls = make_request("/api/v1/admin/classes", method="POST", data=class_payload, headers=admin_headers)
    assert status == 201, f"Create class failed: {cls}"
    class_id = cls["id"]
    print(f"[PASS] Class created over HTTP: ID #{class_id} - '{cls['name']}'")

    # 4. Create Subject
    subj_payload = {
        "code": f"EC{uid[:4].upper()}",
        "name": f"Embedded Systems {uid}",
        "department": f"ECE_{uid}",
    }
    status, subj = make_request("/api/v1/admin/subjects", method="POST", data=subj_payload, headers=admin_headers)
    assert status == 201, f"Create subject failed: {subj}"
    subject_id = subj["id"]
    print(f"[PASS] Subject created over HTTP: ID #{subject_id} - '{subj['name']}'")

    # 5. Create Teachers
    ct_uname = f"ct_{uid}"
    status, ct = make_request(
        "/api/v1/admin/teachers",
        method="POST",
        data={
            "username": ct_uname,
            "full_name": "Dr. Rajesh K",
            "email": f"rajesh_{uid}@college.edu",
            "phone": "+91-9876500001",
            "department": f"ECE_{uid}",
            "role": "CLASS_TEACHER",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    assert status == 201, f"Create class teacher failed: {ct}"
    ct_id = ct["id"]

    st_uname = f"st_{uid}"
    status, st = make_request(
        "/api/v1/admin/teachers",
        method="POST",
        data={
            "username": st_uname,
            "full_name": "Prof. Meena S",
            "email": f"meena_{uid}@college.edu",
            "phone": "+91-9876500002",
            "department": f"ECE_{uid}",
            "role": "SUBJECT_TEACHER",
            "password": "Password@123",
        },
        headers=admin_headers,
    )
    assert status == 201, f"Create subject teacher failed: {st}"
    st_id = st["id"]
    print(f"[PASS] Faculty created over HTTP: CT ID #{ct_id}, ST ID #{st_id}")

    # 6. Assign Teachers
    status, assign_ct = make_request(
        f"/api/v1/admin/classes/{class_id}/assign-teacher",
        method="PUT",
        data={"class_teacher_id": ct_id},
        headers=admin_headers,
    )
    assert status == 200, f"Assign class teacher failed: {assign_ct}"

    status, assign_st = make_request(
        "/api/v1/admin/assignments",
        method="POST",
        data={"class_id": class_id, "subject_id": subject_id, "teacher_id": st_id},
        headers=admin_headers,
    )
    assert status == 201, f"Assign subject teacher failed: {assign_st}"
    print("[PASS] Teachers assigned to Class and Course successfully over HTTP.")

    # 7. Create Student
    s_payload = {
        "class_id": class_id,
        "roll_number": f"EC401_{uid}",
        "register_number": f"REG-EC401_{uid}",
        "full_name": "Priya Sharma",
        "department": f"ECE_{uid}",
        "year": 4,
        "section": "A",
        "email": f"priya_{uid}@college.edu",
        "phone": "+91-9123450010",
    }
    status, student = make_request("/api/v1/admin/students", method="POST", data=s_payload, headers=admin_headers)
    assert status == 201, f"Create student failed: {student}"
    student_id = student["id"]
    print(f"[PASS] Student created over HTTP: ID #{student_id} - '{student['full_name']}'")

    # 8. Class Teacher Login & Face Upload
    status, ct_auth = make_request("/auth/login", method="POST", data={"username": ct_uname, "password": "Password@123"})
    assert status == 200, f"Class teacher login failed: {ct_auth}"
    ct_token = ct_auth["access_token"]
    ct_headers = {"Authorization": f"Bearer {ct_token}"}

    # Upload face with multipart/form-data
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    img_bytes = load_file("student_priya.jpg")
    body_parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="priya.jpg"\r\n'.encode("utf-8"),
        b"Content-Type: image/jpeg\r\n\r\n",
        img_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    raw_multipart = b"".join(body_parts)
    status, enr = make_request(
        f"/api/v1/teachers/class-teacher/students/{student_id}/upload-face",
        method="POST",
        raw_body=raw_multipart,
        content_type=f"multipart/form-data; boundary={boundary}",
        headers=ct_headers,
    )
    assert status == 200, f"Face upload failed: {enr}"
    assert enr["face_enrolled"] is True
    print(f"[PASS] Face enrolled over live HTTP: 128D embedding extracted and verified.")

    # 9. Subject Teacher Login & Classroom Photo Analysis
    status, st_auth = make_request("/auth/login", method="POST", data={"username": st_uname, "password": "Password@123"})
    assert status == 200, f"Subject teacher login failed: {st_auth}"
    st_token = st_auth["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # Multipart for classroom photo analysis
    classroom_bytes = load_file("classroom_alex_priya.jpg")
    boundary2 = "----WebKitFormBoundary" + uuid.uuid4().hex
    form_fields = {
        "class_id": str(class_id),
        "subject_id": str(subject_id),
        "period": "1",
        "date_str": date.today().isoformat(),
        "threshold": "0.45",
    }
    body_parts2 = []
    for k, v in form_fields.items():
        body_parts2.append(f"--{boundary2}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8"))
    body_parts2.append(
        f'--{boundary2}\r\nContent-Disposition: form-data; name="photo"; filename="classroom.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode("utf-8")
    )
    body_parts2.append(classroom_bytes)
    body_parts2.append(f"\r\n--{boundary2}--\r\n".encode("utf-8"))

    status, analysis = make_request(
        "/api/v1/attendance/analyze-classroom-photo",
        method="POST",
        raw_body=b"".join(body_parts2),
        content_type=f"multipart/form-data; boundary={boundary2}",
        headers=st_headers,
    )
    assert status == 200, f"Analyze classroom photo failed: {analysis}"
    assert analysis["present_count"] == 1
    assert analysis["total_faces_detected"] >= 2
    student_preview = analysis["preview_records"][0]
    assert student_preview["student_id"] == student_id
    assert student_preview["status"] == "PRESENT"
    print(f"[PASS] Classroom photo analyzed over live HTTP: Priya Sharma recognized with {student_preview['confidence']}% confidence!")

    # 10. Confirm Attendance
    confirm_payload = {
        "confirmed_records": [{
            "student_id": student_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": st_id,
            "date": date.today().isoformat(),
            "period": 1,
            "status": "PRESENT",
            "confidence": student_preview["confidence"],
            "attendance_image_id": analysis["attendance_image_id"],
            "is_manual": False,
        }]
    }
    status, saved = make_request("/api/v1/attendance/confirm", method="POST", data=confirm_payload, headers=st_headers)
    assert status == 200, f"Confirm attendance failed: {saved}"
    print(f"[PASS] Attendance confirmed and committed to database over live HTTP ({len(saved)} record).")

    # 11. Reports & Percentage Calculation
    status, rep = make_request(f"/api/v1/attendance/reports/student?class_id={class_id}&subject_id={subject_id}", headers=admin_headers)
    assert status == 200, f"Student report failed: {rep}"
    student_row = rep["rows"][0]
    assert student_row["student_id"] == student_id
    assert student_row["attendance_percentage"] == 100.0
    print(f"[PASS] Attendance percentage verified via Reports API: {student_row['attendance_percentage']}% (1/1 session present).")

    print("\n" + "=" * 75)
    print("ALL LIVE HTTP NETWORK REQUESTS VERIFIED 100% SUCCESSFUL!")
    print("=" * 75)


if __name__ == "__main__":
    test_live_http_end_to_end()
