from typing import Optional, List
from datetime import date, datetime
import json
import io
import logging
from pathlib import Path
from uuid import uuid4
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.models.academic import Class, Subject, ClassSubject
from app.models.student import Student
from app.models.attendance import Attendance, AttendanceImage, AttendanceStatus
from app.api.deps import require_subject_teacher, require_class_teacher, require_admin, get_current_user
from app.services.face_recognition import face_recognition_service
from app.services.reports_service import reports_service
from app.schemas.attendance import (
    AttendanceRecordBase,
    AttendanceRecordResponse,
    AttendanceImageResponse,
    AttendanceConfirmationRequest,
    AttendanceAnalysisResponse,
    StudentAttendancePreview,
    UnknownDetection,
)

logger = logging.getLogger("one-click-attendance.api.attendance")

router = APIRouter(prefix="/attendance", tags=["Attendance Processing & Reports"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_CLASSROOM_PHOTO_SIZE = 15 * 1024 * 1024  # 15 Megabytes


def validate_classroom_photo_bytes(photo: UploadFile, photo_bytes: bytes) -> str:
    """
    Validates uploaded classroom photo:
    - Extension check
    - MIME check
    - Size check (500B to 15MB)
    - PIL raster verification
    Returns canonical extension.
    """
    if not photo.filename:
        raise HTTPException(status_code=400, detail="Photo filename is missing.")

    file_ext = Path(photo.filename).suffix.lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image format '{file_ext}'. Allowed formats: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )

    if photo.content_type and photo.content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type '{photo.content_type}'. Must be JPEG, PNG, or WebP.",
        )

    if not photo_bytes or len(photo_bytes) < 500:
        raise HTTPException(status_code=400, detail="Uploaded photo file is empty or corrupted.")

    if len(photo_bytes) > MAX_CLASSROOM_PHOTO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Classroom image exceeds maximum limit of {MAX_CLASSROOM_PHOTO_SIZE // (1024 * 1024)}MB.",
        )

    # Validate PIL raster integrity
    try:
        img = Image.open(io.BytesIO(photo_bytes))
        img_format = img.format.upper() if img.format else ""
        if img_format not in {"JPEG", "PNG", "WEBP"}:
            raise HTTPException(status_code=400, detail=f"Image format '{img_format}' is not permitted.")
        width, height = img.size
        if width < 32 or height < 32:
            raise HTTPException(status_code=400, detail="Classroom photo dimensions are too small (min 32x32px).")
        if width > 12000 or height > 12000:
            raise HTTPException(status_code=400, detail="Classroom photo dimensions exceed maximum limit of 12000x12000px.")
        return ".jpg" if img_format == "JPEG" else f".{img_format.lower()}"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Corrupted or invalid image file: {str(exc)}")


def check_teacher_class_subject_access(teacher: User, class_id: int, subject_id: int, db: Session) -> bool:
    """Verifies that teacher is authorized to access and mark attendance for the given class and subject."""
    if teacher.role == UserRole.ADMIN:
        return True

    # If teacher is the designated class mentor of this class section
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if class_obj and class_obj.class_teacher_id == teacher.id:
        return True

    # If teacher is assigned to this class and subject in ClassSubject
    assignment = db.query(ClassSubject).filter(
        ClassSubject.class_id == class_id,
        ClassSubject.subject_id == subject_id,
        ClassSubject.teacher_id == teacher.id,
    ).first()
    return assignment is not None


@router.post("/analyze", response_model=AttendanceAnalysisResponse)
@router.post("/analyze-classroom-photo", response_model=AttendanceAnalysisResponse)
async def analyze_classroom_photo(
    class_id: int = Form(...),
    subject_id: int = Form(...),
    period: int = Form(1),
    date_str: Optional[str] = Form(None),
    threshold: Optional[float] = Form(None),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: User = Depends(require_subject_teacher),
):
    """
    Analyzes a classroom group photograph:
    1. Validates teacher authorization for class and subject.
    2. Validates raster integrity, MIME type, and size of classroom image.
    3. Securely stores the image with randomized UUID filename.
    4. Runs Computer Vision multi-face detection and 128D embedding extraction.
    5. Matches faces EXCLUSIVELY against enrolled students for the given class_id.
    6. Generates an annotated image with bounding boxes and recognized student names.
    7. Generates an in-memory Attendance Preview mapping present and absent students.
    8. CRITICAL: Does NOT save records into attendance table immediately!
    """
    logger.info(
        f"Analyzing classroom photo for class_id={class_id}, subject_id={subject_id}, "
        f"period={period}, teacher='{current_teacher.username}', filename='{photo.filename}'"
    )

    # Validate class and subject existence
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Selected class not found.")

    subject_obj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject_obj:
        raise HTTPException(status_code=404, detail="Selected subject not found.")

    # 1. Enforce Teacher Class & Subject Authorization
    if not check_teacher_class_subject_access(current_teacher, class_id, subject_id, db):
        logger.warning(
            f"Unauthorized attendance analysis attempt by '{current_teacher.username}' "
            f"for class_id={class_id}, subject_id={subject_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to analyze or mark attendance for this class and subject.",
        )

    # Read and thoroughly validate image contents
    photo_bytes = await photo.read()
    canonical_ext = validate_classroom_photo_bytes(photo, photo_bytes)

    # Determine attendance session date
    session_date = date.today()
    if date_str:
        try:
            session_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            session_date = date.today()

    # Save classroom photo securely to data/attendance_photos with non-predictable UUID filename
    settings.setup_directories()
    safe_filename = f"classroom_c{class_id}_s{subject_id}_{int(datetime.now().timestamp())}_{uuid4().hex[:8]}{canonical_ext}"
    dest_path = settings.ATTENDANCE_PHOTOS_DIR / safe_filename
    with open(dest_path, "wb") as f:
        f.write(photo_bytes)

    # Create AttendanceImage record in database
    attendance_image = AttendanceImage(
        image_path=safe_filename,
        uploaded_by_teacher_id=current_teacher.id,
        class_id=class_id,
        subject_id=subject_id,
        total_faces_detected=0,
    )
    db.add(attendance_image)
    db.commit()
    db.refresh(attendance_image)

    # Run computer vision recognition strictly scoped to this class
    summary = face_recognition_service.recognize_class_attendance(
        db=db,
        class_id=class_id,
        image_data=photo_bytes,
        threshold=threshold,
    )

    # Update total_faces_detected on the image record
    attendance_image.total_faces_detected = summary.total_faces_detected
    db.commit()

    # Generate annotated classroom image with bounding boxes and recognized labels
    annotated_filename = f"annotated_{safe_filename}"
    annotated_dest_path = settings.ATTENDANCE_PHOTOS_DIR / annotated_filename
    try:
        annotated_bytes = face_recognition_service.annotate_image(photo_bytes, summary.matches)
        with open(annotated_dest_path, "wb") as f:
            f.write(annotated_bytes)
        annotated_image_url = f"/attendance_photos/{annotated_filename}"
        annotated_image_path = annotated_filename
    except Exception as e:
        logger.warning(f"Failed to generate annotated classroom image: {e}")
        annotated_image_url = f"/attendance_photos/{safe_filename}"
        annotated_image_path = safe_filename

    # Retrieve all active students belonging to this class
    students = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.is_active == True)
        .order_by(Student.roll_number.asc())
        .all()
    )

    # Map matched face results by student_id
    matched_by_student_id = {
        m.student_id: m for m in summary.matches if m.is_recognized and m.student_id is not None
    }

    preview_records: List[StudentAttendancePreview] = []
    for student in students:
        if student.id in matched_by_student_id:
            m = matched_by_student_id[student.id]
            preview_records.append(
                StudentAttendancePreview(
                    student_id=student.id,
                    roll_number=student.roll_number,
                    register_number=student.register_number,
                    full_name=student.full_name,
                    status="PRESENT",
                    confidence=round(m.similarity * 100.0, 1),
                    similarity=round(m.similarity, 4),
                    is_detected=True,
                    face_enrolled=student.face_enrolled,
                    bounding_box=m.box,
                )
            )
        else:
            preview_records.append(
                StudentAttendancePreview(
                    student_id=student.id,
                    roll_number=student.roll_number,
                    register_number=student.register_number,
                    full_name=student.full_name,
                    status="ABSENT",
                    confidence=0.0,
                    similarity=0.0,
                    is_detected=False,
                    face_enrolled=student.face_enrolled,
                    bounding_box=None,
                )
            )

    # Unknown or low confidence detections
    unknown_list: List[UnknownDetection] = [
        UnknownDetection(
            box=m.box,
            detection_confidence=round(m.detection_confidence, 4),
            similarity=round(m.similarity, 4),
            status=m.status,
        )
        for m in summary.matches
        if not m.is_recognized
    ]

    present_count = sum(1 for p in preview_records if p.status == "PRESENT")
    absent_count = len(preview_records) - present_count

    logger.info(
        f"Attendance analysis complete: {present_count} present, {absent_count} absent "
        f"across {len(students)} students in class '{class_obj.name}'"
    )

    return AttendanceAnalysisResponse(
        attendance_image_id=attendance_image.id,
        image_url=f"/attendance_photos/{safe_filename}",
        image_path=safe_filename,
        annotated_image_url=annotated_image_url,
        annotated_image_path=annotated_image_path,
        class_id=class_id,
        class_name=class_obj.name,
        subject_id=subject_id,
        subject_name=subject_obj.name,
        date=str(session_date),
        period=period,
        threshold_applied=summary.threshold,
        total_students_in_class=len(students),
        total_faces_detected=summary.total_faces_detected,
        recognized_count=summary.recognized_count,
        unknown_count=summary.unknown_count,
        present_count=present_count,
        absent_count=absent_count,
        preview_records=preview_records,
        unknown_detections=unknown_list,
    )


@router.post("/process-classroom-photo", response_model=AttendanceImageResponse)
async def process_classroom_photo(
    department: str = Form(...),
    subject_name: str = Form(...),
    year: int = Form(...),
    section: str = Form(...),
    period: int = Form(1),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: User = Depends(require_subject_teacher),
):
    """
    Direct Attendance Image storage endpoint with authenticated access.
    Validates uploaded photo, saves with secure randomized UUID filename,
    and prevents directory traversal.
    """
    class_name = f"{department} Year {year} Sec {section}"
    class_obj = db.query(Class).filter(
        Class.department == department,
        Class.year == year,
        Class.section == section,
    ).first()
    if not class_obj:
        class_obj = Class(
            name=class_name,
            department=department,
            year=year,
            section=section,
        )
        db.add(class_obj)
        db.commit()
        db.refresh(class_obj)

    subject_code = f"SUB-{subject_name[:4].upper()}"
    subject_obj = db.query(Subject).filter(Subject.name == subject_name).first()
    if not subject_obj:
        subject_obj = Subject(
            code=subject_code,
            name=subject_name,
            department=department,
        )
        db.add(subject_obj)
        db.commit()
        db.refresh(subject_obj)

    # Validate image bytes and format
    photo_bytes = await photo.read()
    canonical_ext = validate_classroom_photo_bytes(photo, photo_bytes)

    # Secure storage with non-predictable UUID filename
    settings.setup_directories()
    safe_filename = f"classroom_c{class_obj.id}_s{subject_obj.id}_{int(datetime.now().timestamp())}_{uuid4().hex[:8]}{canonical_ext}"
    dest_path = settings.ATTENDANCE_PHOTOS_DIR / safe_filename
    with open(dest_path, "wb") as f:
        f.write(photo_bytes)

    new_image = AttendanceImage(
        image_path=safe_filename,
        uploaded_by_teacher_id=current_teacher.id,
        class_id=class_obj.id,
        subject_id=subject_obj.id,
        total_faces_detected=0,
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    return new_image


@router.post("/confirm", response_model=List[AttendanceRecordResponse])
def confirm_attendance(
    confirmation: AttendanceConfirmationRequest,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(require_subject_teacher),
):
    """
    Saves or updates verified student attendance records after teacher confirmation.
    Performs upsert (update if record exists for same student+date+period+subject; otherwise insert).
    Enforces that faculty can only submit and modify attendance for assigned courses and sections.
    """
    logger.info(
        f"Confirming {len(confirmation.confirmed_records)} attendance records by '{current_teacher.username}'"
    )

    # 1. Enforce class and subject authorization for every record submitted
    for rec in confirmation.confirmed_records:
        if not check_teacher_class_subject_access(current_teacher, rec.class_id, rec.subject_id, db):
            logger.warning(
                f"Teacher '{current_teacher.username}' attempted unauthorized attendance modification "
                f"for class {rec.class_id}, subject {rec.subject_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You are not authorized to mark or modify attendance for class ID {rec.class_id} and subject ID {rec.subject_id}.",
            )

    # Validate that no student is submitted more than once in the same confirmation payload
    seen_student_keys = set()
    for rec in confirmation.confirmed_records:
        key = (rec.student_id, rec.class_id, rec.subject_id, rec.date, rec.period)
        if key in seen_student_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate attendance entry for student ID {rec.student_id} in period {rec.period} on {rec.date}. A student cannot be marked twice for the same class, subject, date and period.",
            )
        seen_student_keys.add(key)

    saved_records = []

    for rec in confirmation.confirmed_records:
        # Check if record already exists for this student on this class, date, period, and subject
        existing = (
            db.query(Attendance)
            .filter(
                Attendance.student_id == rec.student_id,
                Attendance.class_id == rec.class_id,
                Attendance.subject_id == rec.subject_id,
                Attendance.date == rec.date,
                Attendance.period == rec.period,
            )
            .first()
        )

        # Enforce authentic teacher attribution: only admin can specify alternative teacher_id
        teacher_id = current_teacher.id if current_teacher.role != UserRole.ADMIN else (rec.teacher_id or current_teacher.id)
        status_enum = (
            rec.status
            if isinstance(rec.status, AttendanceStatus)
            else AttendanceStatus(rec.status)
        )

        if existing:
            existing.status = status_enum
            existing.confidence = rec.confidence
            existing.is_manual = rec.is_manual
            existing.teacher_id = teacher_id
            if rec.attendance_image_id:
                existing.attendance_image_id = rec.attendance_image_id
            if rec.bounding_box:
                existing.bounding_box = (
                    json.dumps(rec.bounding_box)
                    if isinstance(rec.bounding_box, (list, dict))
                    else str(rec.bounding_box)
                )
            saved_records.append(existing)
        else:
            box_str = (
                json.dumps(rec.bounding_box)
                if isinstance(rec.bounding_box, (list, dict))
                else (str(rec.bounding_box) if rec.bounding_box else None)
            )
            attendance_entry = Attendance(
                student_id=rec.student_id,
                class_id=rec.class_id,
                subject_id=rec.subject_id,
                teacher_id=teacher_id,
                date=rec.date,
                period=rec.period,
                status=status_enum,
                confidence=rec.confidence,
                attendance_image_id=rec.attendance_image_id,
                bounding_box=box_str,
                is_manual=rec.is_manual,
            )
            db.add(attendance_entry)
            saved_records.append(attendance_entry)

    db.commit()

    # Populate student names and roll numbers for response
    for entry in saved_records:
        db.refresh(entry)
        if entry.student:
            entry.student_roll = entry.student.roll_number
            entry.student_name = entry.student.full_name

    logger.info(f"Successfully saved {len(saved_records)} attendance records.")
    return saved_records


# -------------------------------------------------------------
# Comprehensive Attendance Reports & CSV Export
# -------------------------------------------------------------

def authorize_and_scope_report(
    current_user: User,
    class_id: Optional[int],
    subject_id: Optional[int],
    teacher_id: Optional[int],
    student_id: Optional[int],
    db: Session,
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """
    Enforces privacy and role-based data boundaries for reports:
    - Admin: unrestricted institution-wide reporting
    - Class Teacher: scoped to their mentored class section or taught courses
    - Subject Teacher: strictly scoped to assigned courses and sections
    """
    if current_user.role == UserRole.ADMIN:
        return class_id, subject_id, teacher_id, student_id

    if current_user.role == UserRole.CLASS_TEACHER:
        mentor_class = db.query(Class).filter(Class.class_teacher_id == current_user.id).first()
        mentor_cid = mentor_class.id if mentor_class else None
        if class_id is not None and mentor_cid and class_id != mentor_cid:
            # Check if teacher teaches a subject in this requested class
            taught = db.query(ClassSubject).filter(
                ClassSubject.teacher_id == current_user.id,
                ClassSubject.class_id == class_id,
            ).first()
            if not taught:
                raise HTTPException(status_code=403, detail="Not authorized to view reports for other classes.")
        elif class_id is None and mentor_cid:
            class_id = mentor_cid
        return class_id, subject_id, teacher_id, student_id

    if current_user.role == UserRole.SUBJECT_TEACHER:
        assigned_cs = db.query(ClassSubject).filter(ClassSubject.teacher_id == current_user.id).all()
        assigned_class_ids = set(cs.class_id for cs in assigned_cs)
        assigned_sub_ids = set(cs.subject_id for cs in assigned_cs)

        if class_id is not None and class_id not in assigned_class_ids:
            raise HTTPException(status_code=403, detail="Not authorized to view reports for unassigned classes.")
        if subject_id is not None and subject_id not in assigned_sub_ids:
            raise HTTPException(status_code=403, detail="Not authorized to view reports for unassigned subjects.")

        # Default teacher_id filter to current teacher if not specified
        if teacher_id is None and not class_id and not subject_id:
            teacher_id = current_user.id

        return class_id, subject_id, teacher_id, student_id

    return class_id, subject_id, teacher_id, student_id


@router.get("/reports/daily")
def get_daily_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    department: Optional[str] = None,
    format: Optional[str] = Query(None, description="Set to 'csv' to download as CSV file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    1. Daily Attendance Report:
    Aggregates daily attendance, day-by-day session breakdowns,
    present count, absent count, total classes, and attendance percentage.
    Requires authentication and enforces role scoping.
    """
    class_id, subject_id, teacher_id, _ = authorize_and_scope_report(
        current_user, class_id, subject_id, teacher_id, None, db
    )
    data = reports_service.get_daily_report(
        db,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        department=department,
    )
    if format == "csv":
        csv_content = reports_service.generate_csv_string(data)
        filename = f"daily_attendance_report_{date.today()}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data


@router.get("/reports/student")
def get_student_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    teacher_id: Optional[int] = None,
    department: Optional[str] = None,
    format: Optional[str] = Query(None, description="Set to 'csv' to download as CSV file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    2. Student Attendance Report:
    Calculates student-wise attendance: present count, absent count,
    total classes, and attendance percentage.
    Requires authentication and protects student privacy.
    """
    class_id, subject_id, teacher_id, student_id = authorize_and_scope_report(
        current_user, class_id, subject_id, teacher_id, student_id, db
    )
    data = reports_service.get_student_report(
        db,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
        student=student,
        teacher_id=teacher_id,
        department=department,
    )
    if format == "csv":
        csv_content = reports_service.generate_csv_string(data)
        filename = f"student_attendance_report_{date.today()}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data


@router.get("/reports/subject")
def get_subject_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    department: Optional[str] = None,
    format: Optional[str] = Query(None, description="Set to 'csv' to download as CSV file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    3. Subject Attendance Report:
    Calculates curriculum subject-wise attendance: present count, absent count,
    total classes conducted, and attendance percentage.
    Requires authentication and enforces subject authorization.
    """
    class_id, subject_id, teacher_id, _ = authorize_and_scope_report(
        current_user, class_id, subject_id, teacher_id, None, db
    )
    data = reports_service.get_subject_report(
        db,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        department=department,
    )
    if format == "csv":
        csv_content = reports_service.generate_csv_string(data)
        filename = f"subject_attendance_report_{date.today()}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data


@router.get("/reports/class")
def get_class_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    class_id: Optional[int] = None,
    department: Optional[str] = None,
    format: Optional[str] = Query(None, description="Set to 'csv' to download as CSV file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    4. Class Attendance Report:
    Calculates cohort class-wise attendance: present count, absent count,
    total classes conducted, enrolled strength, and attendance percentage.
    Requires authentication and enforces role scoping.
    """
    class_id, _, _, _ = authorize_and_scope_report(
        current_user, class_id, None, None, None, db
    )
    data = reports_service.get_class_report(
        db,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        department=department,
    )
    if format == "csv":
        csv_content = reports_service.generate_csv_string(data)
        filename = f"class_attendance_report_{date.today()}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data


@router.get("/reports/monthly")
def get_monthly_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    department: Optional[str] = None,
    format: Optional[str] = Query(None, description="Set to 'csv' to download as CSV file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    5. Monthly Attendance Report:
    Calculates month-by-month attendance: working days, total classes conducted,
    present count, absent count, total records, and monthly attendance percentage.
    Requires authentication and enforces role scoping.
    """
    class_id, subject_id, _, _ = authorize_and_scope_report(
        current_user, class_id, subject_id, None, None, db
    )
    data = reports_service.get_monthly_report(
        db,
        start_date=start_date,
        end_date=end_date,
        year=year,
        month=month,
        class_id=class_id,
        subject_id=subject_id,
        department=department,
    )
    if format == "csv":
        csv_content = reports_service.generate_csv_string(data)
        filename = f"monthly_attendance_report_{date.today()}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data


@router.get("/reports/export-csv")
def export_attendance_report_csv(
    report_type: str = Query("daily", description="Report type: daily, student, subject, class, monthly"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    teacher_id: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exports any attendance report as an official CSV file with UTF-8 encoding
    and standard institutional metadata headers. Requires authentication.
    """
    class_id, subject_id, teacher_id, student_id = authorize_and_scope_report(
        current_user, class_id, subject_id, teacher_id, student_id, db
    )
    try:
        report_data = reports_service.get_report(
            report_type=report_type,
            db=db,
            start_date=start_date,
            end_date=end_date,
            year=year,
            month=month,
            class_id=class_id,
            subject_id=subject_id,
            student_id=student_id,
            student=student,
            teacher_id=teacher_id,
            department=department,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    csv_content = reports_service.generate_csv_string(report_data)
    clean_rt = report_type.lower().strip()
    filename = f"attendance_{clean_rt}_report_{date.today()}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get("/reports/{report_type}/csv")
def export_specific_report_csv(
    report_type: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    teacher_id: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convenience endpoint to download CSV for a specific report type. Requires authentication."""
    return export_attendance_report_csv(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        year=year,
        month=month,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
        student=student,
        teacher_id=teacher_id,
        department=department,
        db=db,
        current_user=current_user,
    )


@router.get("/reports")
def get_attendance_reports(
    report_type: Optional[str] = Query(None, description="One of: daily, student, subject, class, monthly"),
    department: Optional[str] = None,
    subject_id: Optional[int] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    teacher_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main Reports endpoint with authentication:
    - If `report_type` is specified, delegates to that report.
    - If `format='csv'`, returns CSV file download.
    - Otherwise returns overview summary with all report statistics.
    """
    class_id, subject_id, teacher_id, student_id = authorize_and_scope_report(
        current_user, class_id, subject_id, teacher_id, student_id, db
    )
    if report_type:
        clean_rt = report_type.lower().strip()
        try:
            report_data = reports_service.get_report(
                report_type=clean_rt,
                db=db,
                start_date=start_date,
                end_date=end_date,
                year=year,
                month=month,
                class_id=class_id,
                subject_id=subject_id,
                student_id=student_id,
                student=student,
                teacher_id=teacher_id,
                department=department,
            )
            if format == "csv":
                csv_content = reports_service.generate_csv_string(report_data)
                filename = f"attendance_{clean_rt}_report_{date.today()}.csv"
                return Response(
                    content=csv_content,
                    media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            return report_data
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # General overview if no specific report_type given
    query = db.query(Attendance)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if teacher_id:
        query = query.filter(Attendance.teacher_id == teacher_id)

    total_records = query.count()
    present_records = query.filter(Attendance.status == AttendanceStatus.PRESENT).count()
    absent_records = total_records - present_records
    rate = round((present_records / total_records * 100.0), 2) if total_records > 0 else 0.0

    distinct_sessions = len(set((r.date, r.period, r.class_id, r.subject_id) for r in query.all()))

    return {
        "report_title": "Attendance Reports Overview",
        "available_reports": [
            {"type": "daily", "title": "Daily Attendance Report", "endpoint": "/api/v1/attendance/reports/daily"},
            {"type": "student", "title": "Student Attendance Report", "endpoint": "/api/v1/attendance/reports/student"},
            {"type": "subject", "title": "Subject Attendance Report", "endpoint": "/api/v1/attendance/reports/subject"},
            {"type": "class", "title": "Class Attendance Report", "endpoint": "/api/v1/attendance/reports/class"},
            {"type": "monthly", "title": "Monthly Attendance Report", "endpoint": "/api/v1/attendance/reports/monthly"},
        ],
        "filter": {
            "department": department,
            "class_id": class_id,
            "subject_id": subject_id,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "summary": {
            "total_classes": distinct_sessions,
            "total_records": total_records,
            "present_count": present_records,
            "absent_count": absent_records,
            "attendance_percentage": rate,
            "overall_attendance_percentage": rate,
        },
    }


# -------------------------------------------------------------
# Role-Specific Attendance Dashboards with Charts & Filters
# -------------------------------------------------------------

@router.get("/dashboard/class-teacher")
def get_class_teacher_attendance_dashboard(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    teacher_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """
    Class Teacher Attendance Dashboard.
    Provides:
    - Today's attendance (present, absent, rate, period breakdown)
    - Class attendance percentage
    - Student-wise attendance (total classes, attended, %, low attendance status)
    - Subject-wise attendance (breakdown across all courses taken by this class)
    - Date-wise attendance (daily timeline trend)
    Filters supported: class, subject, student, teacher, date range.
    """
    if class_id is not None:
        target_class = db.query(Class).filter(Class.id == class_id).first()
        if not target_class:
            raise HTTPException(status_code=404, detail="Class not found.")
        if current_teacher.role == UserRole.CLASS_TEACHER and target_class.class_teacher_id != current_teacher.id:
            raise HTTPException(status_code=403, detail="You are not authorized for this class.")
    else:
        target_class = db.query(Class).filter(Class.class_teacher_id == current_teacher.id).first()
        if not target_class and current_teacher.role == UserRole.ADMIN:
            target_class = db.query(Class).first()
        if not target_class:
            raise HTTPException(status_code=404, detail="No class assigned to this teacher.")

    students_query = db.query(Student).filter(Student.class_id == target_class.id)
    att_query = db.query(Attendance).filter(Attendance.class_id == target_class.id)

    # Student filter (supports integer ID or roll/name search)
    if student:
        clean_student = student.strip()
        if clean_student.isdigit():
            s_id = int(clean_student)
            students_query = students_query.filter(Student.id == s_id)
            att_query = att_query.filter(Attendance.student_id == s_id)
        else:
            matching_s_ids = [
                s.id for s in db.query(Student).filter(
                    Student.class_id == target_class.id,
                    (Student.roll_number.ilike(f"%{clean_student}%")) |
                    (Student.full_name.ilike(f"%{clean_student}%")) |
                    (Student.register_number.ilike(f"%{clean_student}%"))
                ).all()
            ]
            students_query = students_query.filter(Student.id.in_(matching_s_ids))
            att_query = att_query.filter(Attendance.student_id.in_(matching_s_ids))
    elif student_id:
        students_query = students_query.filter(Student.id == student_id)
        att_query = att_query.filter(Attendance.student_id == student_id)

    if subject_id:
        att_query = att_query.filter(Attendance.subject_id == subject_id)
    if teacher_id:
        att_query = att_query.filter(Attendance.teacher_id == teacher_id)
    if start_date:
        att_query = att_query.filter(Attendance.date >= start_date)
    if end_date:
        att_query = att_query.filter(Attendance.date <= end_date)

    class_students = students_query.order_by(Student.roll_number.asc()).all()
    filtered_records = att_query.all()

    total_records = len(filtered_records)
    present_count = sum(1 for r in filtered_records if r.status == AttendanceStatus.PRESENT)
    absent_count = total_records - present_count
    overall_attendance_rate = round((present_count / total_records * 100.0), 1) if total_records > 0 else 0.0
    distinct_sessions = len(set((r.date, r.period, r.subject_id) for r in filtered_records))

    today = date.today()
    today_records = [r for r in filtered_records if r.date == today]
    today_present = sum(1 for r in today_records if r.status == AttendanceStatus.PRESENT)
    today_absent = len(today_records) - today_present
    today_rate = round((today_present / len(today_records) * 100.0), 1) if today_records else None
    today_sessions = len(set((r.date, r.period, r.subject_id) for r in today_records))

    today_periods = []
    periods_in_today = sorted(list(set(r.period for r in today_records)))
    for p in periods_in_today:
        p_recs = [r for r in today_records if r.period == p]
        p_pres = sum(1 for r in p_recs if r.status == AttendanceStatus.PRESENT)
        p_sub = p_recs[0].subject.name if p_recs and p_recs[0].subject else f"Period {p}"
        p_code = p_recs[0].subject.code if p_recs and p_recs[0].subject else ""
        p_teacher = p_recs[0].teacher.full_name if p_recs and p_recs[0].teacher else "Teacher"
        today_periods.append({
            "period": p,
            "subject_name": p_sub,
            "subject_code": p_code,
            "teacher_name": p_teacher,
            "total_records": len(p_recs),
            "present_count": p_pres,
            "present": p_pres,
            "absent_count": len(p_recs) - p_pres,
            "absent": len(p_recs) - p_pres,
            "rate": round((p_pres / len(p_recs) * 100.0), 1) if p_recs else 0.0,
        })

    student_wise = []
    for s in class_students:
        s_recs = [r for r in filtered_records if r.student_id == s.id]
        s_pres = sum(1 for r in s_recs if r.status == AttendanceStatus.PRESENT)
        s_abs = len(s_recs) - s_pres
        s_rate = round((s_pres / len(s_recs) * 100.0), 1) if s_recs else 0.0
        status_label = "Good" if s_rate >= 75.0 else ("Low Attendance" if s_recs else "No Records")
        student_wise.append({
            "id": s.id,
            "student_id": s.id,
            "roll_number": s.roll_number,
            "register_number": s.register_number,
            "full_name": s.full_name,
            "face_enrolled": s.face_enrolled,
            "total_sessions": len(s_recs),
            "attended_sessions": s_pres,
            "absent_sessions": s_abs,
            "attendance_rate": s_rate,
            "status_label": status_label,
            "is_low_attendance": s_rate < 75.0 and len(s_recs) > 0,
        })

    class_subs = db.query(ClassSubject).filter(ClassSubject.class_id == target_class.id).all()
    subject_wise = []
    for cs in class_subs:
        if subject_id and cs.subject_id != subject_id:
            continue
        sub_recs = [r for r in filtered_records if r.subject_id == cs.subject_id]
        sub_pres = sum(1 for r in sub_recs if r.status == AttendanceStatus.PRESENT)
        sub_rate = round((sub_pres / len(sub_recs) * 100.0), 1) if sub_recs else 0.0
        sub_sessions = len(set((r.date, r.period) for r in sub_recs))
        subject_wise.append({
            "subject_id": cs.subject_id,
            "subject_name": cs.subject.name if cs.subject else "Unknown",
            "subject_code": cs.subject.code if cs.subject else "N/A",
            "code": cs.subject.code if cs.subject else "N/A",
            "teacher_name": cs.teacher.full_name if cs.teacher else "Unassigned",
            "total_sessions": sub_sessions,
            "sessions_count": sub_sessions,
            "sessions_taken": sub_sessions,
            "total_records": len(sub_recs),
            "records_count": len(sub_recs),
            "records_marked": len(sub_recs),
            "present_count": sub_pres,
            "present": sub_pres,
            "absent_count": len(sub_recs) - sub_pres,
            "absent": len(sub_recs) - sub_pres,
            "attendance_rate": sub_rate,
        })

    dates_present = sorted(list(set(r.date for r in filtered_records)))
    date_wise = []
    for d in dates_present:
        d_recs = [r for r in filtered_records if r.date == d]
        d_pres = sum(1 for r in d_recs if r.status == AttendanceStatus.PRESENT)
        d_sessions = len(set((r.period, r.subject_id) for r in d_recs))
        d_rate = round((d_pres / len(d_recs) * 100.0), 1) if d_recs else 0.0
        date_wise.append({
            "date": str(d),
            "sessions_count": d_sessions,
            "total_records": len(d_recs),
            "records_count": len(d_recs),
            "present_count": d_pres,
            "present": d_pres,
            "absent_count": len(d_recs) - d_pres,
            "absent": len(d_recs) - d_pres,
            "attendance_rate": d_rate,
        })

    # Available filter options for the frontend UI
    allowed_classes = db.query(Class).all() if current_teacher.role == UserRole.ADMIN else db.query(Class).filter(Class.class_teacher_id == current_teacher.id).all()
    all_class_students = db.query(Student).filter(Student.class_id == target_class.id).order_by(Student.roll_number.asc()).all()
    assigned_teachers = list({cs.teacher for cs in class_subs if cs.teacher})

    return {
        "class_info": {
            "id": target_class.id,
            "name": target_class.name,
            "department": target_class.department,
            "year": target_class.year,
            "section": target_class.section,
            "class_teacher_name": target_class.class_teacher.full_name if target_class.class_teacher else current_teacher.full_name,
            "total_students": len(all_class_students),
        },
        "today": {
            "date": str(today),
            "sessions_count": today_sessions,
            "total_sessions": today_sessions,
            "total_records": len(today_records),
            "present": today_present,
            "present_count": today_present,
            "absent": today_absent,
            "absent_count": today_absent,
            "attendance_rate": today_rate if today_rate is not None else 0.0,
            "has_data": len(today_records) > 0,
            "periods": today_periods,
        },
        "overall": {
            "total_students": len(all_class_students),
            "total_sessions": distinct_sessions,
            "total_records": total_records,
            "present": present_count,
            "present_count": present_count,
            "absent": absent_count,
            "absent_count": absent_count,
            "attendance_rate": overall_attendance_rate,
            "class_attendance_percentage": overall_attendance_rate,
        },
        "student_wise": student_wise,
        "subject_wise": subject_wise,
        "date_wise": date_wise,
        "available_filters": {
            "classes": [{"id": c.id, "name": c.name} for c in allowed_classes],
            "subjects": [{"id": cs.subject_id, "name": cs.subject.name if cs.subject else "Unknown", "code": cs.subject.code if cs.subject else ""} for cs in class_subs],
            "teachers": [{"id": t.id, "name": t.full_name} for t in assigned_teachers],
            "students": [{"id": s.id, "roll_number": s.roll_number, "full_name": s.full_name} for s in all_class_students],
        },
        "filters_applied": {
            "class_id": target_class.id,
            "subject_id": subject_id,
            "student_id": student_id,
            "student": student,
            "teacher_id": teacher_id,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
    }


@router.get("/dashboard/subject-teacher")
def get_subject_teacher_attendance_dashboard(
    teacher_id: Optional[int] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    """
    Subject Teacher Attendance Dashboard.
    Provides:
    - Attendance taken by them (overall summary)
    - Class-wise records (comparison of classes taught)
    - Subject-wise records (comparison of subjects taught)
    - Date-wise records (chronological session trend and history)
    Filters supported: class, subject, student, date range.
    """
    target_teacher_id = teacher_id if (current_teacher.role == UserRole.ADMIN and teacher_id) else current_teacher.id
    target_user = db.query(User).filter(User.id == target_teacher_id).first() or current_teacher

    query = db.query(Attendance).filter(Attendance.teacher_id == target_teacher_id)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)

    # Student filter support
    if student:
        clean_student = student.strip()
        if clean_student.isdigit():
            query = query.filter(Attendance.student_id == int(clean_student))
        else:
            matching_s_ids = [
                s.id for s in db.query(Student).filter(
                    (Student.roll_number.ilike(f"%{clean_student}%")) |
                    (Student.full_name.ilike(f"%{clean_student}%")) |
                    (Student.register_number.ilike(f"%{clean_student}%"))
                ).all()
            ]
            query = query.filter(Attendance.student_id.in_(matching_s_ids))
    elif student_id:
        query = query.filter(Attendance.student_id == student_id)

    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    records = query.all()

    total_records = len(records)
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = total_records - present_count
    attendance_rate = round((present_count / total_records * 100.0), 1) if total_records > 0 else 0.0
    distinct_sessions = len(set((r.class_id, r.subject_id, r.date, r.period) for r in records))

    assigned_cs = db.query(ClassSubject).filter(ClassSubject.teacher_id == target_teacher_id).all()
    assigned_class_ids = set(cs.class_id for cs in assigned_cs)
    record_class_ids = set(r.class_id for r in records)
    all_class_ids = sorted(list(assigned_class_ids | record_class_ids))

    class_wise = []
    for cid in all_class_ids:
        if class_id and cid != class_id:
            continue
        c_obj = db.query(Class).filter(Class.id == cid).first()
        if not c_obj:
            continue
        c_recs = [r for r in records if r.class_id == cid]
        c_pres = sum(1 for r in c_recs if r.status == AttendanceStatus.PRESENT)
        c_sessions = len(set((r.date, r.period, r.subject_id) for r in c_recs))
        c_rate = round((c_pres / len(c_recs) * 100.0), 1) if c_recs else 0.0
        class_wise.append({
            "class_id": c_obj.id,
            "class_name": c_obj.name,
            "department": c_obj.department,
            "year": c_obj.year,
            "section": c_obj.section,
            "sessions_taken": c_sessions,
            "sessions_count": c_sessions,
            "records_count": len(c_recs),
            "records_marked": len(c_recs),
            "present_count": c_pres,
            "present": c_pres,
            "absent_count": len(c_recs) - c_pres,
            "absent": len(c_recs) - c_pres,
            "attendance_rate": c_rate,
        })

    assigned_sub_ids = set(cs.subject_id for cs in assigned_cs)
    record_sub_ids = set(r.subject_id for r in records)
    all_sub_ids = sorted(list(assigned_sub_ids | record_sub_ids))

    subject_wise = []
    for sid in all_sub_ids:
        if subject_id and sid != subject_id:
            continue
        s_obj = db.query(Subject).filter(Subject.id == sid).first()
        if not s_obj:
            continue
        s_recs = [r for r in records if r.subject_id == sid]
        s_pres = sum(1 for r in s_recs if r.status == AttendanceStatus.PRESENT)
        s_sessions = len(set((r.date, r.period, r.class_id) for r in s_recs))
        s_rate = round((s_pres / len(s_recs) * 100.0), 1) if s_recs else 0.0
        subject_wise.append({
            "subject_id": s_obj.id,
            "subject_name": s_obj.name,
            "subject_code": s_obj.code,
            "code": s_obj.code,
            "department": s_obj.department,
            "sessions_taken": s_sessions,
            "sessions_count": s_sessions,
            "records_count": len(s_recs),
            "records_marked": len(s_recs),
            "present_count": s_pres,
            "present": s_pres,
            "absent_count": len(s_recs) - s_pres,
            "absent": len(s_recs) - s_pres,
            "attendance_rate": s_rate,
        })

    dates_list = sorted(list(set(r.date for r in records)))
    date_wise = []
    for d in dates_list:
        d_recs = [r for r in records if r.date == d]
        d_pres = sum(1 for r in d_recs if r.status == AttendanceStatus.PRESENT)
        d_sessions = len(set((r.period, r.class_id, r.subject_id) for r in d_recs))
        d_rate = round((d_pres / len(d_recs) * 100.0), 1) if d_recs else 0.0
        date_wise.append({
            "date": str(d),
            "sessions_count": d_sessions,
            "total_records": len(d_recs),
            "records_count": len(d_recs),
            "present_count": d_pres,
            "present": d_pres,
            "absent_count": len(d_recs) - d_pres,
            "absent": len(d_recs) - d_pres,
            "attendance_rate": d_rate,
        })

    session_keys = sorted(
        list(set((r.date, r.period, r.class_id, r.subject_id) for r in records)),
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )[:25]

    recent_sessions = []
    for (s_date, s_period, s_class_id, s_sub_id) in session_keys:
        s_recs = [
            r for r in records
            if r.date == s_date and r.period == s_period and r.class_id == s_class_id and r.subject_id == s_sub_id
        ]
        c_obj = db.query(Class).filter(Class.id == s_class_id).first()
        sub_obj = db.query(Subject).filter(Subject.id == s_sub_id).first()
        s_pres = sum(1 for r in s_recs if r.status == AttendanceStatus.PRESENT)
        s_img_id = s_recs[0].attendance_image_id if s_recs else None
        recent_sessions.append({
            "date": str(s_date),
            "period": s_period,
            "class_id": s_class_id,
            "class_name": c_obj.name if c_obj else f"Class {s_class_id}",
            "subject_id": s_sub_id,
            "subject_name": sub_obj.name if sub_obj else f"Subject {s_sub_id}",
            "subject_code": sub_obj.code if sub_obj else "",
            "total_students": len(s_recs),
            "total_marked": len(s_recs),
            "present_count": s_pres,
            "present": s_pres,
            "absent_count": len(s_recs) - s_pres,
            "absent": len(s_recs) - s_pres,
            "attendance_rate": round((s_pres / len(s_recs) * 100.0), 1) if s_recs else 0.0,
            "attendance_image_id": s_img_id,
        })

    # Available classes and subjects for filter dropdowns
    available_classes = [
        {"id": c.id, "name": c.name}
        for c in db.query(Class).filter(Class.id.in_(all_class_ids)).all()
    ]
    available_subjects = [
        {"id": s.id, "name": s.name, "code": s.code}
        for s in db.query(Subject).filter(Subject.id.in_(all_sub_ids)).all()
    ]

    return {
        "teacher_info": {
            "id": target_user.id,
            "full_name": target_user.full_name,
            "username": target_user.username,
            "role": target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role),
            "department": target_user.department,
        },
        "summary": {
            "total_sessions_taken": distinct_sessions,
            "sessions_count": distinct_sessions,
            "total_records_marked": total_records,
            "total_records": total_records,
            "present_count": present_count,
            "present": present_count,
            "absent_count": absent_count,
            "absent": absent_count,
            "attendance_rate": attendance_rate,
        },
        "class_wise": class_wise,
        "subject_wise": subject_wise,
        "date_wise": date_wise,
        "recent_sessions": recent_sessions,
        "available_filters": {
            "classes": available_classes,
            "subjects": available_subjects,
        },
        "filters_applied": {
            "teacher_id": target_teacher_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "student_id": student_id,
            "student": student,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
    }


@router.get("/dashboard/admin")
def get_admin_attendance_dashboard(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    student_id: Optional[int] = None,
    student: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin Attendance Dashboard.
    Provides:
    - All classes (attendance performance across every class)
    - All subjects (curriculum attendance breakdown)
    - Attendance statistics (institution-wide KPIs and trend)
    - Teacher attendance activity (activity ranking and session count)
    Filters supported: class, subject, student, teacher, date range.
    """
    query = db.query(Attendance)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if teacher_id:
        query = query.filter(Attendance.teacher_id == teacher_id)

    # Safe student filter: handles roll number, full name search, or integer ID string
    if student:
        clean_student = student.strip()
        if clean_student.isdigit():
            query = query.filter(Attendance.student_id == int(clean_student))
        else:
            matching_s_ids = [
                s.id for s in db.query(Student).filter(
                    (Student.roll_number.ilike(f"%{clean_student}%")) |
                    (Student.full_name.ilike(f"%{clean_student}%")) |
                    (Student.register_number.ilike(f"%{clean_student}%"))
                ).all()
            ]
            query = query.filter(Attendance.student_id.in_(matching_s_ids))
    elif student_id:
        query = query.filter(Attendance.student_id == student_id)

    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    records = query.all()

    total_records = len(records)
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = total_records - present_count
    overall_rate = round((present_count / total_records * 100.0), 1) if total_records > 0 else 0.0
    distinct_sessions = len(set((r.class_id, r.subject_id, r.date, r.period) for r in records))

    today = date.today()
    today_records = [r for r in records if r.date == today]
    today_present = sum(1 for r in today_records if r.status == AttendanceStatus.PRESENT)
    today_rate = round((today_present / len(today_records) * 100.0), 1) if today_records else 0.0
    today_sessions_count = len(set((r.class_id, r.subject_id, r.period) for r in today_records))

    all_classes_objs = db.query(Class).all()
    all_classes = []
    for c in all_classes_objs:
        if class_id and c.id != class_id:
            continue
        c_recs = [r for r in records if r.class_id == c.id]
        c_pres = sum(1 for r in c_recs if r.status == AttendanceStatus.PRESENT)
        c_sessions = len(set((r.date, r.period, r.subject_id) for r in c_recs))
        c_rate = round((c_pres / len(c_recs) * 100.0), 1) if c_recs else 0.0
        all_classes.append({
            "class_id": c.id,
            "class_name": c.name,
            "name": c.name,
            "department": c.department,
            "year": c.year,
            "section": c.section,
            "class_teacher_name": c.class_teacher.full_name if c.class_teacher else "Unassigned",
            "student_count": len(c.students),
            "sessions_count": c_sessions,
            "sessions_taken": c_sessions,
            "records_count": len(c_recs),
            "records_marked": len(c_recs),
            "present_count": c_pres,
            "present": c_pres,
            "absent_count": len(c_recs) - c_pres,
            "absent": len(c_recs) - c_pres,
            "attendance_rate": c_rate,
            "status_label": "Good Standing" if c_rate >= 75.0 else ("Attention Needed" if c_recs else "No Sessions"),
        })

    all_subjects_objs = db.query(Subject).all()
    all_subjects = []
    for s in all_subjects_objs:
        if subject_id and s.id != subject_id:
            continue
        s_recs = [r for r in records if r.subject_id == s.id]
        s_pres = sum(1 for r in s_recs if r.status == AttendanceStatus.PRESENT)
        s_sessions = len(set((r.date, r.period, r.class_id) for r in s_recs))
        s_rate = round((s_pres / len(s_recs) * 100.0), 1) if s_recs else 0.0
        teachers_assigned = list(set(cs.teacher.full_name for cs in s.class_subjects if cs.teacher))
        classes_linked = set(cs.class_id for cs in s.class_subjects if cs.class_id)
        all_subjects.append({
            "subject_id": s.id,
            "subject_name": s.name,
            "name": s.name,
            "subject_code": s.code,
            "code": s.code,
            "department": s.department,
            "assigned_teachers": teachers_assigned,
            "assigned_teachers_count": len(teachers_assigned),
            "classes_count": len(classes_linked),
            "sessions_count": s_sessions,
            "sessions_taken": s_sessions,
            "records_count": len(s_recs),
            "records_marked": len(s_recs),
            "present_count": s_pres,
            "present": s_pres,
            "absent_count": len(s_recs) - s_pres,
            "absent": len(s_recs) - s_pres,
            "attendance_rate": s_rate,
        })

    all_teachers_objs = db.query(User).filter(User.role.in_([UserRole.SUBJECT_TEACHER, UserRole.CLASS_TEACHER, UserRole.ADMIN])).all()
    teacher_activity = []
    for t in all_teachers_objs:
        if teacher_id and t.id != teacher_id:
            continue
        t_recs = [r for r in records if r.teacher_id == t.id]
        t_sessions = len(set((r.date, r.period, r.class_id, r.subject_id) for r in t_recs))
        t_pres = sum(1 for r in t_recs if r.status == AttendanceStatus.PRESENT)
        t_rate = round((t_pres / len(t_recs) * 100.0), 1) if t_recs else 0.0
        dates_active = [r.date for r in t_recs]
        last_active = str(max(dates_active)) if dates_active else "No Activity"
        assigned_cs = db.query(ClassSubject).filter(ClassSubject.teacher_id == t.id).all()
        assigned_subject_names = list(set(cs.subject.name for cs in assigned_cs if cs.subject))

        teacher_activity.append({
            "teacher_id": t.id,
            "teacher_name": t.full_name,
            "username": t.username,
            "role": t.role.value if hasattr(t.role, "value") else str(t.role),
            "department": t.department,
            "assigned_subjects": assigned_subject_names,
            "sessions_taken": t_sessions,
            "sessions_count": t_sessions,
            "records_marked": len(t_recs),
            "records_count": len(t_recs),
            "present_count": t_pres,
            "present": t_pres,
            "absent_count": len(t_recs) - t_pres,
            "absent": len(t_recs) - t_pres,
            "attendance_rate": t_rate,
            "last_active_date": last_active,
            "is_active": t_sessions > 0,
        })
    teacher_activity.sort(key=lambda x: (x["sessions_taken"], x["records_marked"]), reverse=True)

    dates_list = sorted(list(set(r.date for r in records)))
    date_wise = []
    for d in dates_list:
        d_recs = [r for r in records if r.date == d]
        d_pres = sum(1 for r in d_recs if r.status == AttendanceStatus.PRESENT)
        d_sessions = len(set((r.period, r.class_id, r.subject_id) for r in d_recs))
        d_rate = round((d_pres / len(d_recs) * 100.0), 1) if d_recs else 0.0
        date_wise.append({
            "date": str(d),
            "sessions_count": d_sessions,
            "total_records": len(d_recs),
            "records_count": len(d_recs),
            "present_count": d_pres,
            "present": d_pres,
            "absent_count": len(d_recs) - d_pres,
            "absent": len(d_recs) - d_pres,
            "attendance_rate": d_rate,
        })

    departments = sorted(list(set(c.department for c in all_classes_objs)))
    dept_wise = []
    for dept in departments:
        dept_classes = [c for c in all_classes_objs if c.department == dept]
        dept_c_ids = [c.id for c in dept_classes]
        dept_recs = [r for r in records if r.class_id in dept_c_ids]
        dept_pres = sum(1 for r in dept_recs if r.status == AttendanceStatus.PRESENT)
        dept_sessions = len(set((r.date, r.period, r.class_id, r.subject_id) for r in dept_recs))
        dept_rate = round((dept_pres / len(dept_recs) * 100.0), 1) if dept_recs else 0.0
        dept_students = sum(len(c.students) for c in dept_classes)
        dept_wise.append({
            "department": dept,
            "classes_count": len(dept_classes),
            "students_count": dept_students,
            "sessions_count": dept_sessions,
            "records_count": len(dept_recs),
            "attendance_rate": dept_rate,
        })

    return {
        "statistics": {
            "total_classes": len(all_classes_objs),
            "total_subjects": len(all_subjects_objs),
            "total_teachers": len(all_teachers_objs),
            "total_students": db.query(Student).count(),
            "total_sessions": distinct_sessions,
            "total_records": total_records,
            "total_attendance_records": total_records,
            "records_marked": total_records,
            "present_count": present_count,
            "total_present": present_count,
            "present": present_count,
            "absent_count": absent_count,
            "total_absent": absent_count,
            "absent": absent_count,
            "overall_attendance_rate": overall_rate,
            "today_attendance_rate": today_rate,
            "today_records_count": len(today_records),
            "today_sessions": today_sessions_count,
            "today_sessions_count": today_sessions_count,
        },
        "all_classes": all_classes,
        "all_subjects": all_subjects,
        "teacher_activity": teacher_activity,
        "date_wise": date_wise,
        "department_wise": dept_wise,
        "available_filters": {
            "classes": [{"id": c.id, "name": c.name} for c in all_classes_objs],
            "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in all_subjects_objs],
            "teachers": [{"id": t.id, "name": t.full_name} for t in all_teachers_objs],
        },
        "filters_applied": {
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "student_id": student_id,
            "student": student,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
    }
