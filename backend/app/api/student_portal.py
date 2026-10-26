"""
Student Portal API — Protected endpoints for STUDENT role.

Sections:
  1. Profile & Overview
  2. Attendance Summary (overall %, subject-wise, monthly, low-attendance warning)
  3. Weekly Timetable
  4. Assignments (list pending/submitted/graded + submit)
  5. Academic Grades / Marks
  6. Announcements & Notices

Authorization rules:
  • STUDENT — only their own linked student record
  • ADMIN   — can view any student's data (via ?student_id param)
"""
import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.academic import Class, Subject, ClassSubject
from app.models.attendance import Attendance, AttendanceStatus
from app.models.college_management import (
    Assignment, AssignmentStatus,
    AssignmentSubmission, SubmissionStatus,
    Timetable, ExamTimetable,
    Announcement, AnnouncementPriority,
    StudentAcademicRecord,
    StudyMaterial,
    CollegeEvent,
    Notification,
)
from app.api.deps import get_current_user

logger = logging.getLogger("one-click-attendance.api.student_portal")

router = APIRouter(
    prefix="/student-portal",
    tags=["Student Portal"],
)

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _get_student(current_user: User, db: Session, student_id: Optional[int] = None) -> Student:
    """
    Resolve the student record for the logged-in user.
    ADMIN can pass ?student_id to inspect any student.
    STUDENT must be linked via user.student_id.
    """
    if current_user.role == UserRole.ADMIN and student_id:
        s = db.query(Student).filter(Student.id == student_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Student not found.")
        return s

    if current_user.role == UserRole.STUDENT:
        if not current_user.student_id:
            raise HTTPException(
                status_code=403,
                detail="Student account not linked to a student record. Contact administrator.",
            )
        s = db.query(Student).filter(Student.id == current_user.student_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Linked student record not found.")
        return s

    raise HTTPException(status_code=403, detail="Access forbidden for this role.")


def _require_student_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.STUDENT, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student portal is only accessible to students.",
        )
    return current_user


# ──────────────────────────────────────────────────────────────────
# 1. PROFILE & OVERVIEW
# ──────────────────────────────────────────────────────────────────

@router.get("/me", summary="Student profile and enrollment status")
def get_my_profile(
    student_id: Optional[int] = Query(None, description="Admin only: inspect a specific student"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return current student's profile, class details, and face enrollment status."""
    student = _get_student(current_user, db, student_id)

    class_info = None
    if student.class_id:
        cls = db.query(Class).filter(Class.id == student.class_id).first()
        if cls:
            class_info = {
                "id": cls.id,
                "name": cls.name,
                "department": cls.department,
                "year": cls.year,
                "section": cls.section,
            }

    # Attendance summary quick stats
    total_records = db.query(Attendance).filter(Attendance.student_id == student.id).count()
    present_records = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.status == AttendanceStatus.PRESENT)
        .count()
    )
    attendance_pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

    # Pending assignments count
    if student.class_id:
        all_assignments = (
            db.query(Assignment)
            .filter(Assignment.class_id == student.class_id, Assignment.status == AssignmentStatus.PUBLISHED)
            .all()
        )
        submitted_ids = {
            sub.assignment_id
            for sub in db.query(AssignmentSubmission).filter(
                AssignmentSubmission.student_id == student.id
            ).all()
        }
        pending_count = sum(1 for a in all_assignments if a.id not in submitted_ids)
    else:
        pending_count = 0

    # Unread notifications count
    unread_notifs = (
        db.query(Notification)
        .filter(
            Notification.recipient_id == current_user.id,
            Notification.read_status == False,
        )
        .count()
    )

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "roll_number": student.roll_number,
            "register_number": student.register_number,
            "department": student.department,
            "year": student.year,
            "section": student.section,
            "email": student.email,
            "phone": student.phone,
            "face_enrolled": student.face_enrolled,
            "is_active": student.is_active,
        },
        "class_info": class_info,
        "quick_stats": {
            "attendance_percentage": attendance_pct,
            "total_sessions": total_records,
            "present_sessions": present_records,
            "pending_assignments": pending_count,
            "unread_notifications": unread_notifs,
            "low_attendance_warning": attendance_pct < 75.0 and total_records > 0,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 2. ATTENDANCE SUMMARY
# ──────────────────────────────────────────────────────────────────

@router.get("/attendance", summary="Personal attendance breakdown")
def get_my_attendance(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return overall %, subject-wise %, monthly breakdown, and low-attendance flag."""
    student = _get_student(current_user, db, student_id)

    records = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id)
        .order_by(Attendance.date.desc())
        .all()
    )

    total = len(records)
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
    overall_pct = round((present_count / total * 100), 1) if total > 0 else 0.0

    # Subject-wise breakdown
    subject_map: Dict[int, Dict] = {}
    for r in records:
        sid = r.subject_id
        if sid not in subject_map:
            subj = db.query(Subject).filter(Subject.id == sid).first()
            subject_map[sid] = {
                "subject_id": sid,
                "subject_name": subj.name if subj else "Unknown",
                "subject_code": subj.code if subj else "",
                "total": 0,
                "present": 0,
                "absent": 0,
                "late": 0,
            }
        subject_map[sid]["total"] += 1
        if r.status == AttendanceStatus.PRESENT:
            subject_map[sid]["present"] += 1
        elif r.status == AttendanceStatus.ABSENT:
            subject_map[sid]["absent"] += 1
        elif r.status == AttendanceStatus.LATE:
            subject_map[sid]["late"] += 1

    subject_breakdown = []
    for sd in subject_map.values():
        t = sd["total"]
        sd["percentage"] = round((sd["present"] / t * 100), 1) if t > 0 else 0.0
        sd["low_attendance"] = sd["percentage"] < 75.0 and t > 0
        subject_breakdown.append(sd)
    subject_breakdown.sort(key=lambda x: x["subject_name"])

    # Monthly breakdown (last 6 months)
    monthly_map: Dict[str, Dict] = {}
    for r in records:
        key = r.date.strftime("%Y-%m") if r.date else None
        if not key:
            continue
        if key not in monthly_map:
            monthly_map[key] = {"month": key, "total": 0, "present": 0}
        monthly_map[key]["total"] += 1
        if r.status == AttendanceStatus.PRESENT:
            monthly_map[key]["present"] += 1

    monthly_list = []
    for m, mv in sorted(monthly_map.items(), reverse=True)[:6]:
        t = mv["total"]
        monthly_list.append({
            "month": mv["month"],
            "total": t,
            "present": mv["present"],
            "percentage": round((mv["present"] / t * 100), 1) if t > 0 else 0.0,
        })
    monthly_list.reverse()

    # Recent records (last 20)
    recent = []
    for r in records[:20]:
        subj = db.query(Subject).filter(Subject.id == r.subject_id).first()
        recent.append({
            "date": str(r.date),
            "period": r.period,
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "is_manual": r.is_manual,
        })

    return {
        "overall": {
            "total": total,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "excused": excused_count,
            "percentage": overall_pct,
            "low_attendance_warning": overall_pct < 75.0 and total > 0,
            "sessions_to_75_pct": max(0, int((0.75 * total - present_count) / 0.25) + 1) if overall_pct < 75.0 else 0,
        },
        "subject_breakdown": subject_breakdown,
        "monthly_trend": monthly_list,
        "recent_records": recent,
    }


# ──────────────────────────────────────────────────────────────────
# 3. TIMETABLE
# ──────────────────────────────────────────────────────────────────

@router.get("/timetable", summary="Weekly class timetable")
def get_my_timetable(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return the weekly timetable grid for the student's class."""
    student = _get_student(current_user, db, student_id)

    if not student.class_id:
        return {"timetable": {}, "exam_timetable": []}

    slots = (
        db.query(Timetable)
        .filter(Timetable.class_id == student.class_id)
        .order_by(Timetable.period)
        .all()
    )

    timetable: Dict[str, List] = {day: [] for day in WEEKDAY_ORDER}
    for slot in slots:
        subj = db.query(Subject).filter(Subject.id == slot.subject_id).first()
        teacher = db.query(User).filter(User.id == slot.teacher_id).first() if slot.teacher_id else None
        day = slot.weekday
        if day in timetable:
            timetable[day].append({
                "period": slot.period,
                "subject": subj.name if subj else "N/A",
                "subject_code": subj.code if subj else "",
                "teacher": teacher.full_name if teacher else "TBA",
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "classroom": slot.classroom or "—",
            })

    # Sort each day's slots by period
    for day in timetable:
        timetable[day].sort(key=lambda x: x["period"])

    # Upcoming exam timetable
    today = date.today()
    exams = (
        db.query(ExamTimetable)
        .filter(ExamTimetable.class_id == student.class_id, ExamTimetable.date >= today)
        .order_by(ExamTimetable.date)
        .limit(10)
        .all()
    )
    exam_list = []
    for e in exams:
        subj = db.query(Subject).filter(Subject.id == e.subject_id).first()
        exam_list.append({
            "exam_name": e.exam_name,
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "date": str(e.date),
            "start_time": e.start_time,
            "end_time": e.end_time,
            "venue": e.venue or "—",
        })

    return {
        "timetable": timetable,
        "exam_timetable": exam_list,
    }


# ──────────────────────────────────────────────────────────────────
# 4. ASSIGNMENTS
# ──────────────────────────────────────────────────────────────────

@router.get("/assignments", summary="List assignments for enrolled subjects")
def get_my_assignments(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return pending, submitted, and graded assignment lists for the student."""
    student = _get_student(current_user, db, student_id)

    if not student.class_id:
        return {"pending": [], "submitted": [], "graded": [], "total_count": 0}

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.class_id == student.class_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
        .order_by(Assignment.deadline)
        .all()
    )

    submissions_map = {
        sub.assignment_id: sub
        for sub in db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.student_id == student.id)
        .all()
    }

    now = datetime.now(timezone.utc)
    pending, submitted, graded = [], [], []

    for a in assignments:
        subj = db.query(Subject).filter(Subject.id == a.subject_id).first()
        teacher = db.query(User).filter(User.id == a.teacher_id).first() if a.teacher_id else None
        deadline_dt = a.deadline.replace(tzinfo=timezone.utc) if a.deadline.tzinfo is None else a.deadline
        is_overdue = deadline_dt < now

        base = {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "teacher": teacher.full_name if teacher else "N/A",
            "deadline": a.deadline.isoformat() if a.deadline else None,
            "maximum_marks": a.maximum_marks,
            "is_overdue": is_overdue,
            "attachments": a.attachments,
        }

        sub = submissions_map.get(a.id)
        if sub:
            sub_data = {
                **base,
                "submission_id": sub.id,
                "submission_text": sub.submission_text,
                "uploaded_file": sub.uploaded_file,
                "submitted_date": sub.submitted_date.isoformat() if sub.submitted_date else None,
                "status": sub.submission_status.value if hasattr(sub.submission_status, "value") else str(sub.submission_status),
                "marks": sub.marks,
                "feedback": sub.feedback,
            }
            if sub.submission_status == SubmissionStatus.GRADED:
                graded.append(sub_data)
            else:
                submitted.append(sub_data)
        else:
            pending.append({**base, "status": "NOT_SUBMITTED"})

    return {
        "pending": pending,
        "submitted": submitted,
        "graded": graded,
        "total_count": len(assignments),
        "pending_count": len(pending),
    }


@router.post("/assignments/{assignment_id}/submit", summary="Submit an assignment")
def submit_assignment(
    assignment_id: int,
    submission_text: Optional[str] = None,
    uploaded_file: Optional[str] = None,
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Submit text or file reference for an assignment (creates or updates submission)."""
    student = _get_student(current_user, db, student_id)

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if assignment.class_id != student.class_id:
        raise HTTPException(status_code=403, detail="Assignment is not for your class.")
    if assignment.status != AssignmentStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Assignment is not accepting submissions.")

    now = datetime.now(timezone.utc)
    deadline_dt = assignment.deadline.replace(tzinfo=timezone.utc) if assignment.deadline.tzinfo is None else assignment.deadline
    is_late = deadline_dt < now

    existing = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == student.id,
        )
        .first()
    )

    if existing:
        if existing.submission_status == SubmissionStatus.GRADED:
            raise HTTPException(status_code=400, detail="Already graded. Cannot resubmit.")
        existing.submission_text = submission_text or existing.submission_text
        existing.uploaded_file = uploaded_file or existing.uploaded_file
        existing.submitted_date = now
        existing.submission_status = SubmissionStatus.LATE if is_late else SubmissionStatus.SUBMITTED
        db.commit()
        db.refresh(existing)
        return {"success": True, "message": "Submission updated.", "submission_id": existing.id, "is_late": is_late}
    else:
        sub = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.id,
            submission_text=submission_text,
            uploaded_file=uploaded_file,
            submitted_date=now,
            submission_status=SubmissionStatus.LATE if is_late else SubmissionStatus.SUBMITTED,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return {"success": True, "message": "Assignment submitted.", "submission_id": sub.id, "is_late": is_late}


# ──────────────────────────────────────────────────────────────────
# 5. GRADES / ACADEMIC RECORDS
# ──────────────────────────────────────────────────────────────────

@router.get("/grades", summary="Student academic records and marks")
def get_my_grades(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return internal assessment marks, semester results, and performance summary."""
    student = _get_student(current_user, db, student_id)

    records = (
        db.query(StudentAcademicRecord)
        .filter(StudentAcademicRecord.student_id == student.id)
        .order_by(StudentAcademicRecord.semester, StudentAcademicRecord.academic_year)
        .all()
    )

    # Group by semester
    semesters: Dict[str, List] = {}
    for r in records:
        subj = db.query(Subject).filter(Subject.id == r.subject_id).first()
        key = f"{r.academic_year} — Semester {r.semester}"
        if key not in semesters:
            semesters[key] = []
        pct = round((r.internal_marks / r.max_marks * 100), 1) if r.max_marks > 0 else 0
        grade = _calc_grade(pct)
        semesters[key].append({
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "assessment_type": r.assessment_type,
            "marks": r.internal_marks,
            "max_marks": r.max_marks,
            "percentage": pct,
            "grade": grade,
            "remarks": r.remarks,
        })

    # Overall performance
    if records:
        total_obtained = sum(r.internal_marks for r in records)
        total_max = sum(r.max_marks for r in records)
        overall_pct = round((total_obtained / total_max * 100), 1) if total_max > 0 else 0.0
    else:
        overall_pct = 0.0

    return {
        "semesters": [{"label": k, "records": v} for k, v in semesters.items()],
        "overall_performance": {
            "percentage": overall_pct,
            "grade": _calc_grade(overall_pct),
            "total_assessments": len(records),
        },
    }


def _calc_grade(pct: float) -> str:
    if pct >= 90:
        return "O (Outstanding)"
    elif pct >= 80:
        return "A+ (Excellent)"
    elif pct >= 70:
        return "A (Very Good)"
    elif pct >= 60:
        return "B+ (Good)"
    elif pct >= 50:
        return "B (Average)"
    elif pct >= 40:
        return "C (Pass)"
    else:
        return "F (Fail)"


# ──────────────────────────────────────────────────────────────────
# 6. ANNOUNCEMENTS
# ──────────────────────────────────────────────────────────────────

@router.get("/announcements", summary="Class and institutional notices")
def get_my_announcements(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return all active announcements visible to this student."""
    student = _get_student(current_user, db, student_id)

    now = datetime.now(timezone.utc)
    query = db.query(Announcement).filter(
        (Announcement.expiry_date == None) | (Announcement.expiry_date >= now),
        Announcement.target_audience.in_(["ALL", "STUDENTS"]),
    )

    if student.class_id:
        query = query.filter(
            (Announcement.target_class_id == None) |
            (Announcement.target_class_id == student.class_id)
        )

    announcements = query.order_by(Announcement.publication_date.desc()).limit(50).all()

    result = []
    for a in announcements:
        author = db.query(User).filter(User.id == a.author_id).first() if a.author_id else None
        result.append({
            "id": a.id,
            "title": a.title,
            "message": a.message,
            "author": author.full_name if author else "Administration",
            "priority": a.priority.value if hasattr(a.priority, "value") else str(a.priority),
            "target_audience": a.target_audience,
            "publication_date": a.publication_date.isoformat() if a.publication_date else None,
            "expiry_date": a.expiry_date.isoformat() if a.expiry_date else None,
        })

    urgent_count = sum(1 for a in result if a["priority"] == "URGENT")
    return {
        "announcements": result,
        "total": len(result),
        "urgent_count": urgent_count,
    }


# ──────────────────────────────────────────────────────────────────
# 7. STUDY MATERIALS
# ──────────────────────────────────────────────────────────────────

@router.get("/materials", summary="Study materials for enrolled subjects")
def get_my_materials(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return uploaded study materials for the student's class."""
    student = _get_student(current_user, db, student_id)

    if not student.class_id:
        return {"materials": []}

    materials = (
        db.query(StudyMaterial)
        .filter(StudyMaterial.class_id == student.class_id)
        .order_by(StudyMaterial.uploaded_date.desc())
        .all()
    )

    result = []
    for m in materials:
        subj = db.query(Subject).filter(Subject.id == m.subject_id).first()
        teacher = db.query(User).filter(User.id == m.teacher_id).first() if m.teacher_id else None
        result.append({
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "teacher": teacher.full_name if teacher else "N/A",
            "file_url": m.file_url,
            "uploaded_date": m.uploaded_date.isoformat() if m.uploaded_date else None,
        })

    return {"materials": result, "total": len(result)}


# ──────────────────────────────────────────────────────────────────
# 8. COLLEGE EVENTS / CALENDAR
# ──────────────────────────────────────────────────────────────────

@router.get("/events", summary="Upcoming college events")
def get_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return upcoming institutional events visible to students."""
    now = datetime.now(timezone.utc)
    events = (
        db.query(CollegeEvent)
        .filter(
            CollegeEvent.date >= now,
            CollegeEvent.audience.in_(["ALL", "STUDENTS"]),
        )
        .order_by(CollegeEvent.date)
        .limit(20)
        .all()
    )

    result = []
    for e in events:
        result.append({
            "id": e.id,
            "title": e.event_title,
            "description": e.description,
            "date": e.date.isoformat() if e.date else None,
            "category": e.category,
            "venue": e.venue,
        })

    return {"events": result, "total": len(result)}


# ──────────────────────────────────────────────────────────────────
# 9. NOTIFICATIONS
# ──────────────────────────────────────────────────────────────────

@router.get("/notifications", summary="In-app notifications for this user")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    notifs = (
        db.query(Notification)
        .filter(Notification.recipient_id == current_user.id)
        .order_by(Notification.created_date.desc())
        .limit(30)
        .all()
    )
    result = []
    for n in notifs:
        result.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type.value if hasattr(n.type, "value") else str(n.type),
            "read": n.read_status,
            "created_date": n.created_date.isoformat() if n.created_date else None,
        })
    unread = sum(1 for n in result if not n["read"])
    return {"notifications": result, "unread_count": unread}


@router.post("/notifications/{notification_id}/read", summary="Mark notification as read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.recipient_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notif.read_status = True
    db.commit()
    return {"success": True}


# ──────────────────────────────────────────────────────────────────
# 10. ONLINE CLASSES (Video meetings, Google Meet, Zoom, Teams)
# ──────────────────────────────────────────────────────────────────

@router.get("/online-classes", summary="Upcoming & past online classes with meeting links")
def get_my_online_classes(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Return scheduled, live, and completed online classes for the student's class."""
    student = _get_student(current_user, db, student_id)

    if not student.class_id:
        return {"upcoming": [], "live": [], "completed": [], "total": 0}

    from app.models.college_management import OnlineClass, OnlineClassStatus

    now = datetime.now(timezone.utc)

    all_classes = (
        db.query(OnlineClass)
        .filter(OnlineClass.class_id == student.class_id)
        .order_by(OnlineClass.start_time.desc())
        .limit(50)
        .all()
    )

    def _fmt_class(oc):
        subj = db.query(Subject).filter(Subject.id == oc.subject_id).first()
        teacher = db.query(User).filter(User.id == oc.teacher_id).first() if oc.teacher_id else None
        st = oc.status.value if hasattr(oc.status, "value") else str(oc.status)
        provider = oc.meeting_provider or "Online"
        # Detect platform icon hint from URL
        url = oc.meeting_url or ""
        platform = "google_meet"
        if "zoom" in url.lower():
            platform = "zoom"
        elif "teams" in url.lower() or "microsoft" in url.lower():
            platform = "teams"
        elif "webex" in url.lower():
            platform = "webex"
        elif "classroom.google" in url.lower():
            platform = "google_classroom"
        return {
            "id": oc.id,
            "title": oc.title,
            "subject": subj.name if subj else "N/A",
            "subject_code": subj.code if subj else "",
            "teacher": teacher.full_name if teacher else "TBA",
            "provider": provider,
            "platform": platform,
            "meeting_url": oc.meeting_url,
            "start_time": oc.start_time.isoformat() if oc.start_time else None,
            "end_time": oc.end_time.isoformat() if oc.end_time else None,
            "status": st,
        }

    upcoming, live, completed = [], [], []
    for oc in all_classes:
        st = oc.status.value if hasattr(oc.status, "value") else str(oc.status)
        data = _fmt_class(oc)
        if st == "LIVE":
            live.append(data)
        elif st in ("SCHEDULED",) or (oc.start_time and oc.start_time.replace(tzinfo=timezone.utc) > now):
            upcoming.append(data)
        else:
            completed.append(data)

    return {
        "upcoming": upcoming,
        "live": live,
        "completed": completed[:10],
        "total": len(all_classes),
        "live_count": len(live),
    }


# ──────────────────────────────────────────────────────────────────
# 11. DASHBOARD SUMMARY (single call for Overview tab)
# ──────────────────────────────────────────────────────────────────

@router.get("/dashboard-summary", summary="Full dashboard summary in one call")
@router.get("/dashboard", summary="Dashboard alias")
def get_dashboard_summary(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_student_or_admin),
) -> Dict[str, Any]:
    """Combined dashboard: profile + quick stats + recent attendance + upcoming + live classes."""
    student = _get_student(current_user, db, student_id)

    # Reuse profile logic
    class_info = None
    if student.class_id:
        cls = db.query(Class).filter(Class.id == student.class_id).first()
        if cls:
            class_info = {
                "id": cls.id,
                "name": cls.name,
                "department": cls.department,
                "year": cls.year,
                "section": cls.section,
            }

    total_records = db.query(Attendance).filter(Attendance.student_id == student.id).count()
    present_count = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.status == AttendanceStatus.PRESENT)
        .count()
    )
    attendance_pct = round((present_count / total_records * 100), 1) if total_records > 0 else 0.0

    # Pending assignments
    pending_count = 0
    if student.class_id:
        all_asgn = (
            db.query(Assignment)
            .filter(Assignment.class_id == student.class_id, Assignment.status == AssignmentStatus.PUBLISHED)
            .all()
        )
        submitted_ids = {
            sub.assignment_id
            for sub in db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.student_id == student.id).all()
        }
        pending_count = sum(1 for a in all_asgn if a.id not in submitted_ids)

    # Unread notifications
    unread_notifs = db.query(Notification).filter(
        Notification.recipient_id == current_user.id,
        Notification.read_status == False,
    ).count()

    # Live / upcoming online classes
    from app.models.college_management import OnlineClass, OnlineClassStatus
    now = datetime.now(timezone.utc)
    live_classes = []
    upcoming_classes = []
    if student.class_id:
        ocs = db.query(OnlineClass).filter(OnlineClass.class_id == student.class_id).all()
        for oc in ocs:
            st = oc.status.value if hasattr(oc.status, "value") else str(oc.status)
            subj = db.query(Subject).filter(Subject.id == oc.subject_id).first()
            teacher = db.query(User).filter(User.id == oc.teacher_id).first() if oc.teacher_id else None
            entry = {
                "id": oc.id, "title": oc.title,
                "subject": subj.name if subj else "N/A",
                "teacher": teacher.full_name if teacher else "TBA",
                "provider": oc.meeting_provider,
                "meeting_url": oc.meeting_url,
                "start_time": oc.start_time.isoformat() if oc.start_time else None,
                "status": st,
            }
            if st == "LIVE":
                live_classes.append(entry)
            elif st == "SCHEDULED":
                upcoming_classes.append(entry)

    # Recent 5 attendance records
    recent_att = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id)
        .order_by(Attendance.date.desc())
        .limit(5)
        .all()
    )
    recent_att_list = []
    for r in recent_att:
        subj = db.query(Subject).filter(Subject.id == r.subject_id).first()
        recent_att_list.append({
            "date": str(r.date),
            "subject": subj.name if subj else "N/A",
            "period": r.period,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        })

    # Urgent announcements
    urgent_notices = []
    if student.class_id:
        notices = db.query(Announcement).filter(
            Announcement.target_audience.in_(["ALL", "STUDENTS"]),
            (Announcement.target_class_id == None) | (Announcement.target_class_id == student.class_id),
            Announcement.priority == AnnouncementPriority.URGENT,
        ).order_by(Announcement.publication_date.desc()).limit(3).all()
        for n in notices:
            author = db.query(User).filter(User.id == n.author_id).first() if n.author_id else None
            urgent_notices.append({
                "id": n.id, "title": n.title, "message": n.message,
                "author": author.full_name if author else "Administration",
            })

    # Today's timetable
    today = datetime.now().strftime("%A")
    today_schedule = []
    if student.class_id:
        slots = (
            db.query(Timetable)
            .filter(Timetable.class_id == student.class_id, Timetable.weekday == today)
            .order_by(Timetable.period)
            .all()
        )
        for slot in slots:
            subj = db.query(Subject).filter(Subject.id == slot.subject_id).first()
            teacher = db.query(User).filter(User.id == slot.teacher_id).first() if slot.teacher_id else None
            today_schedule.append({
                "period": slot.period,
                "subject": subj.name if subj else "N/A",
                "teacher": teacher.full_name if teacher else "TBA",
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "classroom": slot.classroom or "—",
            })

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "roll_number": student.roll_number,
            "register_number": student.register_number,
            "department": student.department,
            "year": student.year,
            "section": student.section,
            "email": student.email,
            "phone": student.phone,
            "face_enrolled": student.face_enrolled,
            "is_active": student.is_active,
        },
        "class_info": class_info,
        "quick_stats": {
            "attendance_percentage": attendance_pct,
            "total_sessions": total_records,
            "present_sessions": present_count,
            "pending_assignments": pending_count,
            "unread_notifications": unread_notifs,
            "low_attendance_warning": attendance_pct < 75.0 and total_records > 0,
            "live_classes_now": len(live_classes),
        },
        "live_classes": live_classes,
        "upcoming_classes": upcoming_classes[:3],
        "recent_attendance": recent_att_list,
        "urgent_notices": urgent_notices,
        "today_schedule": today_schedule,
        "today": today,
    }
