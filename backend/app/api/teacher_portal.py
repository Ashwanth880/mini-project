"""
Teacher Portal API — Protected endpoints for CLASS_TEACHER and SUBJECT_TEACHER roles.

Sections:
  1. Dashboard Overview
  2. My Classes & Subjects
  3. Assignment Management (CRUD + Grading)
  4. Online Classes (Schedule / Update / Cancel)
  5. Study Materials (Upload / Update / Delete)
  6. Timetable (Weekly view + slot management)
  7. College Calendar (Events + Exams + Deadlines)
  8. Announcements (Publish / Edit / Delete)
  9. Student Performance (Attendance + Marks)

Authorization rules:
  • SUBJECT_TEACHER  — only their own assigned classes/subjects
  • CLASS_TEACHER    — above + their mentored class
  • ADMIN            — unrestricted
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.academic import Class, Subject, ClassSubject
from app.models.attendance import Attendance
from app.models.college_management import (
    Assignment, AssignmentStatus,
    AssignmentSubmission, SubmissionStatus,
    OnlineClass, OnlineClassStatus,
    Timetable, ExamTimetable,
    CollegeEvent, Announcement,
    StudyMaterial, Notification, NotificationType,
)
from app.schemas.college_management import (
    AssignmentCreate, AssignmentUpdate,
    AssignmentSubmissionUpdate,
    OnlineClassCreate, OnlineClassUpdate,
    TimetableCreate,
    ExamTimetableCreate,
    CollegeEventCreate,
    AnnouncementCreate, AnnouncementUpdate,
    StudyMaterialCreate, StudyMaterialUpdate,
)
from app.api.deps import require_subject_teacher

logger = logging.getLogger("one-click-attendance.api.teacher_portal")

router = APIRouter(
    prefix="/teacher-portal",
    tags=["Teacher Portal"],
    dependencies=[Depends(require_subject_teacher)],
)


# ──────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────────────────────────

def _class_ids_for(teacher: User, db: Session) -> List[int]:
    """All class IDs accessible to this teacher."""
    if teacher.role == UserRole.ADMIN:
        return [r[0] for r in db.query(Class.id).all()]
    ids = [
        r[0] for r in
        db.query(ClassSubject.class_id)
        .filter(ClassSubject.teacher_id == teacher.id).all()
    ]
    if teacher.role == UserRole.CLASS_TEACHER:
        mentored = db.query(Class).filter(Class.class_teacher_id == teacher.id).all()
        for c in mentored:
            if c.id not in ids:
                ids.append(c.id)
    return list(set(ids))


def _assert_class(class_id: int, teacher: User, db: Session) -> Class:
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")
    if teacher.role != UserRole.ADMIN and class_id not in _class_ids_for(teacher, db):
        raise HTTPException(status_code=403, detail="Not assigned to this class.")
    return c


def _assert_owns_assignment(a: Assignment, teacher: User) -> None:
    if teacher.role != UserRole.ADMIN and a.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You do not own this assignment.")


def _is_present(v) -> bool:
    if not v:
        return False
    return (v.value if hasattr(v, "value") else str(v)) == "PRESENT"


# ──────────────────────────────────────────────────────────────────
# 1. DASHBOARD OVERVIEW
# ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def teacher_dashboard(
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Teacher dashboard: assigned classes, today's timetable, upcoming classes,
    pending evaluations, recent announcements."""

    class_ids = _class_ids_for(teacher, db)

    # Assigned classes / subjects
    assigned_classes = []
    subject_ids = set()
    for cid in class_ids:
        c = db.query(Class).filter(Class.id == cid).first()
        if not c:
            continue
        if teacher.role == UserRole.SUBJECT_TEACHER:
            cs_rows = db.query(ClassSubject).filter(
                ClassSubject.class_id == cid,
                ClassSubject.teacher_id == teacher.id,
            ).all()
        else:
            cs_rows = db.query(ClassSubject).filter(ClassSubject.class_id == cid).all()

        if cs_rows:
            for cs in cs_rows:
                if cs.subject:
                    subject_ids.add(cs.subject.id)
                    assigned_classes.append({
                        "class_subject_id": cs.id,
                        "class_id": cs.class_id,
                        "class_name": c.name,
                        "department": c.department,
                        "year": c.year,
                        "section": c.section,
                        "subject_id": cs.subject_id,
                        "subject_name": cs.subject.name,
                        "subject_code": cs.subject.code,
                    })
        else:
            assigned_classes.append({
                "class_subject_id": 0,
                "class_id": c.id,
                "class_name": c.name,
                "department": c.department,
                "year": c.year,
                "section": c.section,
                "subject_id": 0,
                "subject_name": "General",
                "subject_code": "GEN",
            })

    # Mentored class
    mentored_class = None
    if teacher.role in (UserRole.CLASS_TEACHER, UserRole.ADMIN):
        mc = db.query(Class).filter(Class.class_teacher_id == teacher.id).first()
        if mc:
            mentored_class = {
                "id": mc.id, "name": mc.name,
                "department": mc.department, "year": mc.year, "section": mc.section,
                "student_count": db.query(Student).filter(Student.class_id == mc.id).count(),
            }

    # Today's timetable
    today_name = datetime.now().strftime("%A")
    todays_timetable = [
        {
            "id": s.id, "period": s.period,
            "subject_name": s.subject.name if s.subject else "N/A",
            "subject_code": s.subject.code if s.subject else "N/A",
            "class_name": s.class_group.name if s.class_group else "N/A",
            "start_time": s.start_time, "end_time": s.end_time,
            "classroom": s.classroom,
        }
        for s in (
            db.query(Timetable)
            .filter(Timetable.teacher_id == teacher.id, Timetable.weekday == today_name)
            .order_by(Timetable.period).all()
        )
    ]

    # Upcoming online classes (next 5)
    now = datetime.now(timezone.utc)
    upcoming_oc = (
        db.query(OnlineClass)
        .filter(
            OnlineClass.teacher_id == teacher.id,
            OnlineClass.start_time >= now,
            OnlineClass.status.in_([OnlineClassStatus.SCHEDULED, OnlineClassStatus.LIVE]),
        )
        .order_by(OnlineClass.start_time).limit(5).all()
    )
    upcoming_online_classes = [
        {
            "id": oc.id, "title": oc.title,
            "subject_name": oc.subject.name if oc.subject else "N/A",
            "class_name": oc.class_group.name if oc.class_group else "N/A",
            "meeting_provider": oc.meeting_provider,
            "meeting_url": oc.meeting_url,
            "start_time": oc.start_time.isoformat() if oc.start_time else None,
            "end_time": oc.end_time.isoformat() if oc.end_time else None,
            "status": oc.status.value if hasattr(oc.status, "value") else str(oc.status),
        }
        for oc in upcoming_oc
    ]

    # Pending evaluations
    my_assign_ids = [
        r[0] for r in
        db.query(Assignment.id).filter(Assignment.teacher_id == teacher.id).all()
    ]
    pending_subs = []
    pending_count = 0
    if my_assign_ids:
        subs = (
            db.query(AssignmentSubmission)
            .filter(
                AssignmentSubmission.assignment_id.in_(my_assign_ids),
                AssignmentSubmission.submission_status == SubmissionStatus.SUBMITTED,
            )
            .limit(10).all()
        )
        pending_count = len(subs)
        for sub in subs[:5]:
            pending_subs.append({
                "submission_id": sub.id,
                "assignment_id": sub.assignment_id,
                "assignment_title": sub.assignment.title if sub.assignment else "N/A",
                "student_name": sub.student.full_name if sub.student else "N/A",
                "student_roll": sub.student.roll_number if sub.student else "N/A",
                "submitted_date": sub.submitted_date.isoformat() if sub.submitted_date else None,
            })

    # Recent announcements (authored by teacher or for their classes)
    ann_filter = [Announcement.author_id == teacher.id, Announcement.target_audience == "ALL"]
    if class_ids:
        ann_filter.append(Announcement.target_class_id.in_(class_ids))
    recent_anns = (
        db.query(Announcement)
        .filter(or_(*ann_filter))
        .order_by(Announcement.publication_date.desc()).limit(5).all()
    )
    recent_announcements = [
        {
            "id": a.id, "title": a.title,
            "message": (a.message or "")[:200],
            "author": a.author.full_name if a.author else "System",
            "priority": a.priority.value if hasattr(a.priority, "value") else str(a.priority),
            "publication_date": a.publication_date.isoformat() if a.publication_date else None,
        }
        for a in recent_anns
    ]

    total_students = sum(
        db.query(Student).filter(Student.class_id == cid).count() for cid in class_ids
    )

    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.full_name,
        "role": teacher.role.value if hasattr(teacher.role, "value") else str(teacher.role),
        "department": teacher.department,
        "mentored_class": mentored_class,
        "assigned_classes": assigned_classes,
        "total_assigned_classes": len(class_ids),
        "total_assigned_subjects": len(subject_ids) if subject_ids else (1 if assigned_classes else 0),
        "total_students": total_students,
        "total_assignments": db.query(Assignment).filter(Assignment.teacher_id == teacher.id).count(),
        "total_study_materials": db.query(StudyMaterial).filter(StudyMaterial.teacher_id == teacher.id).count(),
        "pending_evaluations": pending_count,
        "todays_timetable": todays_timetable,
        "upcoming_online_classes": upcoming_online_classes,
        "pending_submission_details": pending_subs,
        "recent_announcements": recent_announcements,
    }


# ──────────────────────────────────────────────────────────────────
# 2. MY CLASSES & SUBJECTS
# ──────────────────────────────────────────────────────────────────

@router.get("/my-classes")
def get_my_classes(
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """All classes & subjects assigned to the logged-in teacher with student rosters."""
    class_ids = _class_ids_for(teacher, db)
    classes_map: Dict[int, Dict] = {}

    for cid in class_ids:
        c = db.query(Class).filter(Class.id == cid).first()
        if not c:
            continue
        students = (
            db.query(Student)
            .filter(Student.class_id == cid)
            .order_by(Student.roll_number).all()
        )
        if teacher.role == UserRole.SUBJECT_TEACHER:
            cs_list = db.query(ClassSubject).filter(
                ClassSubject.class_id == cid,
                ClassSubject.teacher_id == teacher.id,
            ).all()
        else:
            cs_list = db.query(ClassSubject).filter(ClassSubject.class_id == cid).all()

        subjects = []
        for cs in cs_list:
            if cs.subject and cs.subject.id not in [s["id"] for s in subjects]:
                subjects.append({
                    "id": cs.subject.id,
                    "name": cs.subject.name,
                    "code": cs.subject.code,
                })

        if not subjects:
            dept_subjects = db.query(Subject).filter(
                or_(Subject.department == c.department, Subject.department == "ALL", Subject.department.is_(None))
            ).all()
            for s in dept_subjects:
                subjects.append({
                    "id": s.id,
                    "name": s.name,
                    "code": s.code,
                })

        classes_map[cid] = {
            "id": c.id,
            "name": c.name,
            "department": c.department,
            "year": c.year,
            "section": c.section,
            "subjects": subjects,
            "students": [
                {
                    "id": s.id, "roll_number": s.roll_number,
                    "full_name": s.full_name, "email": s.email,
                    "is_active": s.is_active, "face_enrolled": s.face_enrolled,
                }
                for s in students
            ],
            "student_count": len(students),
        }

    return {"teacher_id": teacher.id, "teacher_name": teacher.full_name, "classes": list(classes_map.values())}


# ──────────────────────────────────────────────────────────────────
# 3. ASSIGNMENT MANAGEMENT
# ──────────────────────────────────────────────────────────────────

@router.get("/assignments")
def list_teacher_assignments(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    assignment_status: Optional[str] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    q = db.query(Assignment)
    if teacher.role != UserRole.ADMIN:
        q = q.filter(Assignment.teacher_id == teacher.id)
    if class_id:
        q = q.filter(Assignment.class_id == class_id)
    if subject_id:
        q = q.filter(Assignment.subject_id == subject_id)
    if assignment_status:
        try:
            q = q.filter(Assignment.status == AssignmentStatus(assignment_status.upper()))
        except ValueError:
            pass
    result = []
    for a in q.order_by(Assignment.created_date.desc()).all():
        sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id).count()
        pending = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == a.id,
            AssignmentSubmission.submission_status == SubmissionStatus.SUBMITTED,
        ).count()
        result.append({
            "id": a.id, "title": a.title, "description": a.description,
            "subject_id": a.subject_id,
            "subject_name": a.subject.name if a.subject else None,
            "subject_code": a.subject.code if a.subject else None,
            "class_id": a.class_id,
            "class_name": a.class_group.name if a.class_group else None,
            "teacher_id": a.teacher_id,
            "created_date": a.created_date.isoformat() if a.created_date else None,
            "deadline": a.deadline.isoformat() if a.deadline else None,
            "maximum_marks": a.maximum_marks,
            "attachments": a.attachments,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "submission_count": sub_count,
            "pending_evaluations": pending,
        })
    return result


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    data: AssignmentCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    _assert_class(data.class_id, teacher, db)
    tid = data.teacher_id if (teacher.role == UserRole.ADMIN and data.teacher_id) else teacher.id
    a = Assignment(
        title=data.title, description=data.description,
        subject_id=data.subject_id, class_id=data.class_id, teacher_id=tid,
        deadline=data.deadline, maximum_marks=data.maximum_marks,
        attachments=data.attachments, status=data.status,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "title": a.title, "status": a.status.value, "message": "Assignment created."}


@router.patch("/assignments/{aid}")
def update_assignment(
    aid: int, data: AssignmentUpdate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    _assert_owns_assignment(a, teacher)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(a, field, val)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "status": a.status.value if hasattr(a.status, "value") else str(a.status), "message": "Updated."}


@router.delete("/assignments/{aid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    aid: int,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    _assert_owns_assignment(a, teacher)
    db.delete(a)
    db.commit()


@router.get("/assignments/{aid}/submissions")
def list_submissions(
    aid: int,
    sub_status: Optional[str] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    _assert_owns_assignment(a, teacher)
    q = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == aid)
    if sub_status:
        try:
            q = q.filter(AssignmentSubmission.submission_status == SubmissionStatus(sub_status.upper()))
        except ValueError:
            pass
    return [
        {
            "id": sub.id, "assignment_id": sub.assignment_id,
            "student_id": sub.student_id,
            "student_name": sub.student.full_name if sub.student else "N/A",
            "student_roll": sub.student.roll_number if sub.student else "N/A",
            "submission_text": sub.submission_text,
            "uploaded_file": sub.uploaded_file,
            "submitted_date": sub.submitted_date.isoformat() if sub.submitted_date else None,
            "marks": sub.marks, "feedback": sub.feedback,
            "submission_status": sub.submission_status.value if hasattr(sub.submission_status, "value") else str(sub.submission_status),
            "max_marks": a.maximum_marks,
        }
        for sub in q.order_by(AssignmentSubmission.submitted_date.desc()).all()
    ]


@router.patch("/assignments/{aid}/submissions/{sid}/grade")
def grade_submission(
    aid: int, sid: int,
    data: AssignmentSubmissionUpdate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    _assert_owns_assignment(a, teacher)
    sub = db.query(AssignmentSubmission).filter(
        AssignmentSubmission.id == sid, AssignmentSubmission.assignment_id == aid
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if data.marks is not None:
        if data.marks > a.maximum_marks:
            raise HTTPException(status_code=400, detail=f"Marks exceed max ({a.maximum_marks}).")
        sub.marks = data.marks
    if data.feedback is not None:
        sub.feedback = data.feedback
    sub.submission_status = data.submission_status or SubmissionStatus.GRADED
    db.commit()
    db.refresh(sub)
    # Notify student
    if sub.student and sub.student.user_account:
        db.add(Notification(
            recipient_id=sub.student.user_account.id,
            title=f"Graded: {a.title}",
            message=f"Marks: {sub.marks}/{a.maximum_marks}",
            type=NotificationType.GRADE,
            related_record=f"assignment:{aid}",
        ))
        db.commit()
    return {"submission_id": sub.id, "marks": sub.marks, "status": sub.submission_status.value, "message": "Graded."}


# ──────────────────────────────────────────────────────────────────
# 4. ONLINE CLASSES
# ──────────────────────────────────────────────────────────────────

@router.get("/online-classes")
def list_online_classes(
    class_id: Optional[int] = None,
    oc_status: Optional[str] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    q = db.query(OnlineClass)
    if teacher.role != UserRole.ADMIN:
        q = q.filter(OnlineClass.teacher_id == teacher.id)
    if class_id:
        q = q.filter(OnlineClass.class_id == class_id)
    if oc_status:
        try:
            q = q.filter(OnlineClass.status == OnlineClassStatus(oc_status.upper()))
        except ValueError:
            pass
    return [
        {
            "id": oc.id, "title": oc.title,
            "subject_name": oc.subject.name if oc.subject else None,
            "class_id": oc.class_id,
            "class_name": oc.class_group.name if oc.class_group else None,
            "meeting_provider": oc.meeting_provider, "meeting_url": oc.meeting_url,
            "start_time": oc.start_time.isoformat() if oc.start_time else None,
            "end_time": oc.end_time.isoformat() if oc.end_time else None,
            "status": oc.status.value if hasattr(oc.status, "value") else str(oc.status),
            "created_date": oc.created_date.isoformat() if oc.created_date else None,
        }
        for oc in q.order_by(OnlineClass.start_time.desc()).all()
    ]


@router.post("/online-classes", status_code=status.HTTP_201_CREATED)
def schedule_online_class(
    data: OnlineClassCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    _assert_class(data.class_id, teacher, db)
    tid = data.teacher_id if (teacher.role == UserRole.ADMIN and data.teacher_id) else teacher.id
    oc = OnlineClass(
        title=data.title, subject_id=data.subject_id, class_id=data.class_id,
        teacher_id=tid, meeting_provider=data.meeting_provider,
        meeting_url=data.meeting_url, start_time=data.start_time,
        end_time=data.end_time, status=data.status,
    )
    db.add(oc)
    db.commit()
    db.refresh(oc)
    return {"id": oc.id, "title": oc.title, "meeting_url": oc.meeting_url,
            "start_time": oc.start_time.isoformat(), "message": "Online class scheduled."}


@router.patch("/online-classes/{oid}")
def update_online_class(
    oid: int, data: OnlineClassUpdate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    oc = db.query(OnlineClass).filter(OnlineClass.id == oid).first()
    if not oc:
        raise HTTPException(status_code=404, detail="Online class not found.")
    if teacher.role != UserRole.ADMIN and oc.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(oc, field, val)
    db.commit()
    db.refresh(oc)
    return {"id": oc.id, "status": oc.status.value if hasattr(oc.status, "value") else str(oc.status), "message": "Updated."}


@router.delete("/online-classes/{oid}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_online_class(
    oid: int,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    oc = db.query(OnlineClass).filter(OnlineClass.id == oid).first()
    if not oc:
        raise HTTPException(status_code=404, detail="Online class not found.")
    if teacher.role != UserRole.ADMIN and oc.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    db.delete(oc)
    db.commit()


# ──────────────────────────────────────────────────────────────────
# 5. STUDY MATERIALS
# ──────────────────────────────────────────────────────────────────

@router.get("/study-materials")
def list_study_materials(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    q = db.query(StudyMaterial)
    if teacher.role != UserRole.ADMIN:
        q = q.filter(StudyMaterial.teacher_id == teacher.id)
    if class_id:
        q = q.filter(StudyMaterial.class_id == class_id)
    if subject_id:
        q = q.filter(StudyMaterial.subject_id == subject_id)
    return [
        {
            "id": m.id, "title": m.title,
            "subject_name": m.subject.name if m.subject else None,
            "class_name": m.class_group.name if m.class_group else None,
            "description": m.description, "file_url": m.file_url,
            "file_size_bytes": m.file_size_bytes,
            "uploaded_date": m.uploaded_date.isoformat() if m.uploaded_date else None,
        }
        for m in q.order_by(StudyMaterial.uploaded_date.desc()).all()
    ]


@router.post("/study-materials", status_code=status.HTTP_201_CREATED)
def upload_study_material(
    data: StudyMaterialCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    _assert_class(data.class_id, teacher, db)
    tid = data.teacher_id if (teacher.role == UserRole.ADMIN and data.teacher_id) else teacher.id
    m = StudyMaterial(
        title=data.title, subject_id=data.subject_id, class_id=data.class_id,
        teacher_id=tid, description=data.description,
        file_url=data.file_url, file_size_bytes=data.file_size_bytes,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "title": m.title, "file_url": m.file_url, "message": "Material uploaded."}


@router.patch("/study-materials/{mid}")
def update_study_material(
    mid: int, data: StudyMaterialUpdate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    m = db.query(StudyMaterial).filter(StudyMaterial.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="Material not found.")
    if teacher.role != UserRole.ADMIN and m.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(m, field, val)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "message": "Updated."}


@router.delete("/study-materials/{mid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_material(
    mid: int,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    m = db.query(StudyMaterial).filter(StudyMaterial.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="Material not found.")
    if teacher.role != UserRole.ADMIN and m.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    db.delete(m)
    db.commit()


# ──────────────────────────────────────────────────────────────────
# 6. TIMETABLE
# ──────────────────────────────────────────────────────────────────

@router.get("/timetable")
def get_timetable(
    class_id: Optional[int] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    q = db.query(Timetable)
    if class_id:
        _assert_class(class_id, teacher, db)
        q = q.filter(Timetable.class_id == class_id)
    elif teacher.role != UserRole.ADMIN:
        cids = _class_ids_for(teacher, db)
        q = q.filter(Timetable.class_id.in_(cids))

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    weekly: Dict[str, List] = {d: [] for d in days}
    for slot in q.all():
        if slot.weekday in weekly:
            weekly[slot.weekday].append({
                "id": slot.id, "period": slot.period,
                "class_id": slot.class_id,
                "class_name": slot.class_group.name if slot.class_group else "N/A",
                "subject_name": slot.subject.name if slot.subject else "N/A",
                "subject_code": slot.subject.code if slot.subject else "N/A",
                "teacher_name": slot.teacher.full_name if slot.teacher else "N/A",
                "start_time": slot.start_time, "end_time": slot.end_time,
                "classroom": slot.classroom,
            })
    for day in weekly:
        weekly[day].sort(key=lambda x: x["period"])
    return {"weekly_timetable": weekly, "today": datetime.now().strftime("%A")}


@router.post("/timetable", status_code=status.HTTP_201_CREATED)
def create_timetable_slot(
    data: TimetableCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    _assert_class(data.class_id, teacher, db)
    conflict = db.query(Timetable).filter(
        Timetable.class_id == data.class_id,
        Timetable.weekday == data.weekday,
        Timetable.period == data.period,
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail=f"Period {data.period} on {data.weekday} is already taken.")
    slot = Timetable(**data.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"id": slot.id, "message": "Timetable slot created."}


@router.delete("/timetable/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timetable_slot(
    slot_id: int,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    slot = db.query(Timetable).filter(Timetable.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found.")
    _assert_class(slot.class_id, teacher, db)
    db.delete(slot)
    db.commit()


# ──────────────────────────────────────────────────────────────────
# 7. COLLEGE CALENDAR
# ──────────────────────────────────────────────────────────────────

@router.get("/calendar")
def get_calendar(
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    class_ids = _class_ids_for(teacher, db)
    items = []

    # Events
    for e in db.query(CollegeEvent).order_by(CollegeEvent.date).all():
        items.append({
            "type": "EVENT", "id": e.id, "title": e.event_title,
            "description": e.description,
            "date": e.date.isoformat() if e.date else None,
            "category": e.category, "audience": e.audience, "venue": e.venue,
        })

    # Exams
    eq = db.query(ExamTimetable)
    if class_ids:
        eq = eq.filter(ExamTimetable.class_id.in_(class_ids))
    for ex in eq.order_by(ExamTimetable.date).all():
        items.append({
            "type": "EXAM", "id": ex.id,
            "title": f"{ex.exam_name} — {ex.subject.name if ex.subject else 'N/A'}",
            "exam_name": ex.exam_name,
            "subject_name": ex.subject.name if ex.subject else "N/A",
            "class_name": ex.class_group.name if ex.class_group else "N/A",
            "date": ex.date.isoformat() if ex.date else None,
            "start_time": ex.start_time, "end_time": ex.end_time, "venue": ex.venue,
        })

    # Assignment deadlines
    for a in db.query(Assignment).filter(Assignment.teacher_id == teacher.id).order_by(Assignment.deadline).all():
        items.append({
            "type": "ASSIGNMENT_DEADLINE", "id": a.id,
            "title": f"Deadline: {a.title}",
            "subject_name": a.subject.name if a.subject else "N/A",
            "class_name": a.class_group.name if a.class_group else "N/A",
            "date": a.deadline.isoformat() if a.deadline else None,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
        })

    # Upcoming online classes
    now = datetime.now(timezone.utc)
    ocs = db.query(OnlineClass).filter(
        OnlineClass.teacher_id == teacher.id,
        OnlineClass.start_time >= now,
    ).order_by(OnlineClass.start_time).all()
    for oc in ocs:
        items.append({
            "type": "ONLINE_CLASS", "id": oc.id, "title": oc.title,
            "subject_name": oc.subject.name if oc.subject else "N/A",
            "class_name": oc.class_group.name if oc.class_group else "N/A",
            "date": oc.start_time.isoformat() if oc.start_time else None,
            "meeting_url": oc.meeting_url,
        })

    items.sort(key=lambda x: x.get("date") or "")
    return {"calendar": items}


@router.post("/calendar/events", status_code=status.HTTP_201_CREATED)
def create_event(
    data: CollegeEventCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    ev = CollegeEvent(
        event_title=data.event_title, description=data.description,
        date=data.date, category=data.category, audience=data.audience,
        venue=data.venue, created_by_user_id=teacher.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"id": ev.id, "event_title": ev.event_title, "message": "Event created."}


@router.post("/calendar/exams", status_code=status.HTTP_201_CREATED)
def create_exam(
    data: ExamTimetableCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    _assert_class(data.class_id, teacher, db)
    ex = ExamTimetable(**data.model_dump())
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return {"id": ex.id, "exam_name": ex.exam_name, "message": "Exam scheduled."}


# ──────────────────────────────────────────────────────────────────
# 8. ANNOUNCEMENTS
# ──────────────────────────────────────────────────────────────────

@router.get("/announcements")
def list_announcements(
    class_id: Optional[int] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    class_ids = _class_ids_for(teacher, db)
    filters = [Announcement.author_id == teacher.id, Announcement.target_audience == "ALL"]
    if class_ids:
        filters.append(Announcement.target_class_id.in_(class_ids))
    if class_id:
        filters = [Announcement.author_id == teacher.id, Announcement.target_class_id == class_id]
    anns = db.query(Announcement).filter(or_(*filters)).order_by(Announcement.publication_date.desc()).all()
    return [
        {
            "id": a.id, "title": a.title, "message": a.message,
            "author_id": a.author_id,
            "author_name": a.author.full_name if a.author else "System",
            "target_class_id": a.target_class_id,
            "target_class_name": a.target_class.name if a.target_class else None,
            "target_audience": a.target_audience,
            "priority": a.priority.value if hasattr(a.priority, "value") else str(a.priority),
            "publication_date": a.publication_date.isoformat() if a.publication_date else None,
            "expiry_date": a.expiry_date.isoformat() if a.expiry_date else None,
        }
        for a in anns
    ]


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
def publish_announcement(
    data: AnnouncementCreate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    if data.target_class_id:
        _assert_class(data.target_class_id, teacher, db)
    ann = Announcement(
        title=data.title, message=data.message,
        author_id=teacher.id, target_class_id=data.target_class_id,
        target_audience=data.target_audience, priority=data.priority,
        expiry_date=data.expiry_date,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"id": ann.id, "title": ann.title, "message": "Announcement published."}


@router.patch("/announcements/{ann_id}")
def update_announcement(
    ann_id: int, data: AnnouncementUpdate,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    if teacher.role != UserRole.ADMIN and ann.author_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(ann, field, val)
    db.commit()
    db.refresh(ann)
    return {"id": ann.id, "message": "Updated."}


@router.delete("/announcements/{ann_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(
    ann_id: int,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    if teacher.role != UserRole.ADMIN and ann.author_id != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    db.delete(ann)
    db.commit()


# ──────────────────────────────────────────────────────────────────
# 9. STUDENT PERFORMANCE
# ──────────────────────────────────────────────────────────────────

@router.get("/student-performance")
@router.get("/performance")
def get_student_performance(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    """Attendance rates, assignment completion, and recorded marks per student."""
    class_ids = _class_ids_for(teacher, db)
    target = [class_id] if class_id else class_ids
    if class_id:
        _assert_class(class_id, teacher, db)

    performance = []
    for cid in target:
        c = db.query(Class).filter(Class.id == cid).first()
        if not c:
            continue
        students = (
            db.query(Student)
            .filter(Student.class_id == cid, Student.is_active.is_(True))
            .all()
        )
        # My assignments for this class
        aq = db.query(Assignment.id).filter(
            Assignment.teacher_id == teacher.id,
            Assignment.class_id == cid,
        )
        if subject_id:
            aq = aq.filter(Assignment.subject_id == subject_id)
        my_aids = [r[0] for r in aq.all()]

        for st in students:
            # Attendance
            att_q = db.query(Attendance).filter(Attendance.student_id == st.id)
            if subject_id:
                att_q = att_q.filter(Attendance.subject_id == subject_id)
            all_att = att_q.all()
            total_att = len(all_att)
            present_att = sum(1 for a in all_att if _is_present(a.status))
            att_rate = round(present_att / total_att * 100, 1) if total_att > 0 else None

            # Marks
            total_marks = 0.0
            max_possible = 0.0
            submitted = 0
            if my_aids:
                subs = db.query(AssignmentSubmission).filter(
                    AssignmentSubmission.student_id == st.id,
                    AssignmentSubmission.assignment_id.in_(my_aids),
                ).all()
                submitted = len(subs)
                for sub in subs:
                    if sub.marks is not None:
                        total_marks += sub.marks
                        a_obj = db.query(Assignment).filter(Assignment.id == sub.assignment_id).first()
                        if a_obj:
                            max_possible += a_obj.maximum_marks

            performance.append({
                "student_id": st.id, "roll_number": st.roll_number,
                "full_name": st.full_name, "class_name": c.name,
                "attendance_rate": att_rate,
                "total_classes": total_att, "present_classes": present_att,
                "assignments_submitted": submitted,
                "total_assignments": len(my_aids),
                "marks_scored": total_marks, "max_possible": max_possible,
                "marks_percentage": round(total_marks / max_possible * 100, 1) if max_possible > 0 else None,
            })

    return {"performance": performance, "total_students": len(performance)}
