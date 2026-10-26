import logging
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, StudentFace
from app.models.academic import Class, Subject, ClassSubject
from app.models.attendance import Attendance, AttendanceStatus
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse,
    SubjectTeacherCreate, SubjectTeacherUpdate,
    SubjectTeacherDetailResponse, SubjectTeacherAssignmentResponse,
    TeacherAssignmentInput,
)
from app.schemas.student import StudentResponse, FaceEnrollmentResponse, ClassTeacherStudentCreate, ClassTeacherStudentUpdate
from app.api.students import format_student_response
from app.utils.security import hash_password
from app.api.deps import require_class_teacher, require_subject_teacher, require_admin, get_current_user
from app.services.face_service import (
    face_service,
    StudentNotFoundError,
    NoFaceDetectedError,
    MultipleFacesDetectedError,
    ImageQualityError,
    InvalidImageError,
    FaceEnrollmentError,
)

logger = logging.getLogger("one-click-attendance.api.teachers")

router = APIRouter(prefix="/teachers", tags=["Teachers"])


def is_present(status_val) -> bool:
    """Safely check if attendance status represents PRESENT regardless of enum or string type."""
    if not status_val:
        return False
    if hasattr(status_val, "value"):
        return status_val.value == "PRESENT"
    return str(status_val) == "PRESENT"


def get_assigned_class_for_teacher(user: User, db: Session, class_id: Optional[int] = None) -> Class:
    """Helper to retrieve authorized assigned class for class teacher or admin."""
    if class_id is not None:
        c = db.query(Class).filter(Class.id == class_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Class not found.")
        if user.role == UserRole.CLASS_TEACHER and c.class_teacher_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized for this class.")
        return c

    # Search assigned class for this class teacher
    assigned = db.query(Class).filter(Class.class_teacher_id == user.id).first()
    if assigned:
        return assigned

    # If Admin, fallback to first class in db if none directly assigned
    if user.role == UserRole.ADMIN:
        first_c = db.query(Class).first()
        if first_c:
            return first_c

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No class is currently assigned to this teacher. Please contact an administrator.",
    )


@router.get("/class-teacher/my-class")
def get_my_assigned_class(
    class_id: Optional[int] = None,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """View assigned class details and roster metrics for the logged-in class teacher."""
    my_class = get_assigned_class_for_teacher(current_teacher, db, class_id)
    students = db.query(Student).filter(Student.class_id == my_class.id).all()
    total_students = len(students)
    active_students = sum(1 for s in students if s.is_active)
    face_enrolled_count = sum(1 for s in students if s.face_enrolled)
    face_rate = round((face_enrolled_count / total_students * 100.0), 1) if total_students > 0 else 0.0

    class_subs = db.query(ClassSubject).filter(ClassSubject.class_id == my_class.id).all()
    subjects_data = []
    for cs in class_subs:
        subjects_data.append({
            "subject_id": cs.subject_id,
            "subject_name": cs.subject.name if cs.subject else "Unknown",
            "subject_code": cs.subject.code if cs.subject else "N/A",
            "teacher_id": cs.teacher_id,
            "teacher_name": cs.teacher.full_name if cs.teacher else "Unassigned",
        })

    attendances = db.query(Attendance).filter(Attendance.class_id == my_class.id).all()
    if attendances:
        present_count = sum(1 for a in attendances if is_present(a.status))
        overall_attendance_rate = round((present_count / len(attendances)) * 100.0, 1)
    else:
        overall_attendance_rate = 100.0 if total_students > 0 else 0.0

    return {
        "id": my_class.id,
        "name": my_class.name,
        "department": my_class.department,
        "year": my_class.year,
        "section": my_class.section,
        "class_teacher_id": my_class.class_teacher_id,
        "class_teacher_name": my_class.class_teacher.full_name if my_class.class_teacher else current_teacher.full_name,
        "total_students": total_students,
        "active_students": active_students,
        "face_enrolled_count": face_enrolled_count,
        "face_enrollment_rate": face_rate,
        "overall_attendance_rate": overall_attendance_rate,
        "subjects": subjects_data,
    }


@router.get("/class-teacher/students", response_model=List[StudentResponse])
def get_class_students(
    class_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    face_status: Optional[str] = None,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """View student list for assigned class with search and filtering."""
    my_class = get_assigned_class_for_teacher(current_teacher, db, class_id)
    query = db.query(Student).filter(Student.class_id == my_class.id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Student.full_name.ilike(s)) |
            (Student.roll_number.ilike(s)) |
            (Student.register_number.ilike(s)) |
            (Student.email.ilike(s))
        )

    if status == "active":
        query = query.filter(Student.is_active == True)
    elif status == "inactive":
        query = query.filter(Student.is_active == False)

    if face_status == "enrolled":
        query = query.filter(Student.face_enrolled == True)
    elif face_status == "pending":
        query = query.filter(Student.face_enrolled == False)

    students = query.order_by(Student.roll_number.asc()).all()
    return [format_student_response(st) for st in students]


@router.post("/class-teacher/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def add_student_to_class(
    student_in: ClassTeacherStudentCreate,
    class_id: Optional[int] = None,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Add a new student directly into assigned class."""
    my_class = get_assigned_class_for_teacher(current_teacher, db, class_id)

    full_name = (student_in.full_name or student_in.name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Student name is required.")

    roll_number = student_in.roll_number.strip()
    if not roll_number:
        raise HTTPException(status_code=400, detail="Roll number is required.")

    register_number = student_in.register_number.strip() if student_in.register_number else f"REG-{roll_number}"

    existing = db.query(Student).filter(
        (Student.roll_number == roll_number) | (Student.register_number == register_number)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student with this roll number or register number already exists.")

    new_student = Student(
        roll_number=roll_number,
        register_number=register_number,
        full_name=full_name,
        department=my_class.department,
        year=my_class.year,
        section=my_class.section,
        class_id=my_class.id,
        email=student_in.email.strip() if student_in.email else None,
        phone=student_in.phone.strip() if student_in.phone else None,
        is_active=True,
        face_enrolled=False,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return format_student_response(new_student)


@router.get("/class-teacher/students/{student_id}", response_model=StudentResponse)
def get_class_student(
    student_id: int,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Retrieve details of a student in the assigned class."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized to access student from another class.")
    return format_student_response(st)


@router.put("/class-teacher/students/{student_id}", response_model=StudentResponse)
def edit_student_info(
    student_id: int,
    student_update: ClassTeacherStudentUpdate,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Edit student information."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized to edit student from another class.")

    name = student_update.full_name or student_update.name
    if name is not None and name.strip():
        st.full_name = name.strip()

    if student_update.roll_number is not None and student_update.roll_number.strip() != st.roll_number:
        r = student_update.roll_number.strip()
        dup = db.query(Student).filter(Student.roll_number == r, Student.id != student_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="Roll number already exists.")
        st.roll_number = r

    if student_update.register_number is not None and student_update.register_number.strip() != st.register_number:
        reg = student_update.register_number.strip()
        dup = db.query(Student).filter(Student.register_number == reg, Student.id != student_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="Register number already exists.")
        st.register_number = reg

    if student_update.email is not None:
        st.email = student_update.email.strip() if student_update.email.strip() else None
    if student_update.phone is not None:
        st.phone = student_update.phone.strip() if student_update.phone.strip() else None
    if student_update.is_active is not None:
        st.is_active = student_update.is_active

    db.commit()
    db.refresh(st)
    return format_student_response(st)


@router.patch("/class-teacher/students/{student_id}/toggle-status", response_model=StudentResponse)
def toggle_class_student_status(
    student_id: int,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Toggle student active/inactive status."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized for this student.")
    st.is_active = not st.is_active
    db.commit()
    db.refresh(st)
    return format_student_response(st)


@router.delete("/class-teacher/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_student(
    student_id: int,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Delete a student from the assigned class."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized for this student.")
    db.delete(st)
    db.commit()
    return None


@router.post("/class-teacher/students/{student_id}/upload-face", response_model=FaceEnrollmentResponse)
def upload_student_face(
    student_id: int,
    file: UploadFile = File(...),
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """
    Upload and securely store student's face photo with full CV detection and embedding pipeline:
    1. Receive image.
    2. Validate file format and size.
    3. Detect faces (require exactly one face).
    4. Perform image quality checks.
    5. Generate 128D face embedding.
    6. Store embedding strictly associated with student.
    7. Store original image securely.
    """
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized for this student.")

    try:
        content = file.file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(exc)}")

    try:
        result = face_service.enroll_student_face(
            db=db,
            student_id=st.id,
            image_bytes=content,
            filename=file.filename or "portrait.jpg",
            content_type=file.content_type,
        )
        return FaceEnrollmentResponse(**result)
    except StudentNotFoundError:
        raise HTTPException(status_code=404, detail="Student not found.")
    except NoFaceDetectedError:
        raise HTTPException(status_code=400, detail="No face detected")
    except MultipleFacesDetectedError:
        raise HTTPException(status_code=400, detail="Multiple faces detected")
    except ImageQualityError as exc:
        logger.warning(f"Image quality check failed: {exc}")
        raise HTTPException(status_code=400, detail="Image quality insufficient")
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(exc)}")
    except FaceEnrollmentError:
        raise HTTPException(status_code=500, detail="Face enrollment failed")


@router.get("/class-teacher/students/{student_id}/face")
def get_student_face_status(
    student_id: int,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """View face enrollment status and image details for a student."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_teacher.role == UserRole.CLASS_TEACHER:
        my_class = get_assigned_class_for_teacher(current_teacher, db)
        if st.class_id != my_class.id:
            raise HTTPException(status_code=403, detail="Not authorized for this student.")

    face = db.query(StudentFace).filter(
        StudentFace.student_id == st.id,
        StudentFace.is_primary == True
    ).first()

    return {
        "student_id": st.id,
        "roll_number": st.roll_number,
        "full_name": st.full_name,
        "face_enrolled": st.face_enrolled,
        "face_image_path": face.image_path if face else None,
        "enrolled_at": face.created_at if face else None,
        "status_label": "Enrolled" if st.face_enrolled else "Pending Enrollment",
    }


@router.get("/class-teacher/attendance-summary")
def get_class_attendance_summary(
    class_id: Optional[int] = None,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """View comprehensive attendance summary for the assigned class."""
    my_class = get_assigned_class_for_teacher(current_teacher, db, class_id)
    students = db.query(Student).filter(Student.class_id == my_class.id).all()
    total_students = len(students)
    active_students = sum(1 for s in students if s.is_active)
    face_enrolled_count = sum(1 for s in students if s.face_enrolled)

    attendances = db.query(Attendance).filter(Attendance.class_id == my_class.id).all()
    total_records = len(attendances)
    present_count = sum(1 for a in attendances if is_present(a.status))
    overall_rate = round((present_count / total_records * 100.0), 1) if total_records > 0 else 0.0

    sessions = set((a.date, a.period, a.subject_id) for a in attendances)
    total_sessions = len(sessions)

    today = date.today()
    today_att = [a for a in attendances if a.date == today]
    today_present = sum(1 for a in today_att if is_present(a.status))
    today_rate = round((today_present / len(today_att) * 100.0), 1) if today_att else None

    class_subs = db.query(ClassSubject).filter(ClassSubject.class_id == my_class.id).all()
    subject_summaries = []
    for cs in class_subs:
        sub_atts = [a for a in attendances if a.subject_id == cs.subject_id]
        sub_present = sum(1 for a in sub_atts if is_present(a.status))
        sub_rate = round((sub_present / len(sub_atts) * 100.0), 1) if sub_atts else None
        sub_sessions = len(set((a.date, a.period) for a in sub_atts))
        subject_summaries.append({
            "subject_id": cs.subject_id,
            "subject_name": cs.subject.name if cs.subject else "Unknown",
            "subject_code": cs.subject.code if cs.subject else "N/A",
            "teacher_name": cs.teacher.full_name if cs.teacher else "Unassigned",
            "total_sessions": sub_sessions,
            "attendance_rate": sub_rate,
        })

    low_attendance_students = []
    for s in students:
        s_atts = [a for a in attendances if a.student_id == s.id]
        if s_atts:
            s_pres = sum(1 for a in s_atts if is_present(a.status))
            s_rate = round((s_pres / len(s_atts)) * 100.0, 1)
            if s_rate < 75.0:
                low_attendance_students.append({
                    "student_id": s.id,
                    "roll_number": s.roll_number,
                    "full_name": s.full_name,
                    "total_classes": len(s_atts),
                    "attended_classes": s_pres,
                    "attendance_rate": s_rate,
                })

    return {
        "class_id": my_class.id,
        "class_name": my_class.name,
        "department": my_class.department,
        "year": my_class.year,
        "section": my_class.section,
        "total_students": total_students,
        "active_students": active_students,
        "face_enrolled_count": face_enrolled_count,
        "face_enrollment_rate": round((face_enrolled_count / total_students * 100.0), 1) if total_students > 0 else 0.0,
        "total_sessions": total_sessions,
        "total_records": total_records,
        "overall_attendance_rate": overall_rate,
        "today_attendance_rate": today_rate,
        "subject_summaries": subject_summaries,
        "low_attendance_students": low_attendance_students,
    }


@router.get("/class-teacher/overview")
def get_class_teacher_overview(
    department: str = "Computer Science",
    year: int = 3,
    section: str = "A",
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """
    Overview data for Class Teacher (legacy compatibility).
    """
    students_count = db.query(Student).filter(
        Student.department == department,
        Student.year == year,
        Student.section == section,
    ).count()

    return {
        "portal": "Class Teacher Portal",
        "teacher_name": current_teacher.full_name,
        "role": current_teacher.role.value if hasattr(current_teacher.role, "value") else str(current_teacher.role),
        "assigned_class": f"{department} - Year {year} Sec {section}",
        "students_count": students_count,
        "daily_attendance_rate": 94.2,
        "recent_alerts": [],
    }


# ===========================================================================
# CLASS TEACHER: SUBJECT TEACHER MANAGEMENT & ASSIGNMENTS
# ===========================================================================

def format_subject_teacher_detail(teacher: User, db: Session) -> SubjectTeacherDetailResponse:
    assignments = db.query(ClassSubject).filter(ClassSubject.teacher_id == teacher.id).all()
    assigned_subjects = []
    for cs in assignments:
        c = cs.class_group
        s = cs.subject
        if c and s:
            assigned_subjects.append(
                SubjectTeacherAssignmentResponse(
                    id=cs.id,
                    class_id=c.id,
                    class_name=c.name,
                    department=c.department,
                    year=c.year,
                    section=c.section,
                    subject_id=s.id,
                    subject_name=s.name,
                    subject_code=s.code,
                )
            )

    role_val = teacher.role.value if hasattr(teacher.role, "value") else str(teacher.role)
    return SubjectTeacherDetailResponse(
        id=teacher.id,
        teacher_id=teacher.teacher_id,
        username=teacher.username,
        email=teacher.email,
        full_name=teacher.full_name,
        role=role_val,
        department=teacher.department,
        is_active=bool(teacher.is_active),
        created_at=teacher.created_at,
        assigned_subjects=assigned_subjects,
        assignments=assigned_subjects,
    )


def _find_subject_teacher(identifier: str, db: Session) -> User:
    query = db.query(User).filter(User.role == UserRole.SUBJECT_TEACHER)
    if identifier.isdigit():
        t = query.filter(User.id == int(identifier)).first()
        if t:
            return t
    t = query.filter((User.teacher_id == identifier) | (User.username == identifier)).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"Subject Teacher '{identifier}' not found.")
    return t


@router.get("/class-teacher/available-assignment-options")
def get_available_assignment_options(
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Return available classes and subjects for assigning subject teachers."""
    classes = db.query(Class).order_by(Class.name).all()
    subjects = db.query(Subject).order_by(Subject.name).all()
    return {
        "classes": [
            {"id": c.id, "name": c.name, "department": c.department, "year": c.year, "section": c.section}
            for c in classes
        ],
        "subjects": [
            {"id": s.id, "name": s.name, "code": s.code, "department": s.department}
            for s in subjects
        ],
    }


@router.get("/class-teacher/subject-teachers", response_model=List[SubjectTeacherDetailResponse])
def get_class_teacher_subject_teachers(
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """List all Subject Teachers with their course assignments."""
    teachers = (
        db.query(User)
        .filter(User.role == UserRole.SUBJECT_TEACHER)
        .order_by(User.full_name)
        .all()
    )
    return [format_subject_teacher_detail(t, db) for t in teachers]


@router.post("/class-teacher/subject-teachers", response_model=SubjectTeacherDetailResponse, status_code=status.HTTP_201_CREATED)
def create_subject_teacher(
    payload: SubjectTeacherCreate,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """
    Create a new Subject Teacher with unique Teacher ID, username, and securely hashed password.
    Optionally assign to specific classes and subjects.
    """
    tid = payload.teacher_id.strip() if payload.teacher_id else ""
    if not tid:
        raise HTTPException(status_code=400, detail="Teacher ID is required.")

    uname = payload.username.strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username is required.")

    name = payload.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Full name is required.")

    pwd = payload.password.strip() if payload.password else ""
    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    # Check Teacher ID uniqueness
    existing_tid = db.query(User).filter(User.teacher_id == tid).first()
    if existing_tid:
        raise HTTPException(status_code=400, detail=f"Teacher ID '{tid}' is already in use.")

    # Check Username uniqueness
    existing_uname = db.query(User).filter(User.username == uname).first()
    if existing_uname:
        raise HTTPException(status_code=400, detail=f"Username '{uname}' already exists.")

    # Derive unique email
    email = (payload.email or f"{uname.lower()}@college.edu").strip().lower()
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        email = f"{uname.lower()}.{tid.lower()}@college.edu"

    department = (payload.department or current_teacher.department or "General").strip()

    # Secure password hashing with bcrypt
    hashed_pwd = hash_password(pwd)

    new_teacher = User(
        teacher_id=tid,
        username=uname,
        email=email,
        full_name=name,
        hashed_password=hashed_pwd,
        role=UserRole.SUBJECT_TEACHER,
        department=department,
        is_active=True,
    )
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)

    # Save assignments if provided
    if payload.assignments:
        for assign in payload.assignments:
            cls = db.query(Class).filter(Class.id == assign.class_id).first()
            subj = db.query(Subject).filter(Subject.id == assign.subject_id).first()
            if not cls or not subj:
                continue
            existing_cs = db.query(ClassSubject).filter(
                ClassSubject.class_id == assign.class_id,
                ClassSubject.subject_id == assign.subject_id,
                ClassSubject.teacher_id == new_teacher.id,
            ).first()
            if not existing_cs:
                cs = ClassSubject(
                    class_id=assign.class_id,
                    subject_id=assign.subject_id,
                    teacher_id=new_teacher.id,
                )
                db.add(cs)
        db.commit()
        db.refresh(new_teacher)

    return format_subject_teacher_detail(new_teacher, db)


@router.get("/class-teacher/subject-teachers/{teacher_identifier}", response_model=SubjectTeacherDetailResponse)
def get_subject_teacher_detail(
    teacher_identifier: str,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """View details and assignments for a single Subject Teacher."""
    teacher = _find_subject_teacher(teacher_identifier, db)
    return format_subject_teacher_detail(teacher, db)


@router.put("/class-teacher/subject-teachers/{teacher_identifier}", response_model=SubjectTeacherDetailResponse)
def update_subject_teacher(
    teacher_identifier: str,
    payload: SubjectTeacherUpdate,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Edit Subject Teacher profile, password, active state, or course assignments."""
    teacher = _find_subject_teacher(teacher_identifier, db)

    if payload.teacher_id is not None:
        tid = payload.teacher_id.strip()
        if tid and tid != teacher.teacher_id:
            existing = db.query(User).filter(User.teacher_id == tid, User.id != teacher.id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Teacher ID '{tid}' is already taken.")
            teacher.teacher_id = tid

    if payload.username is not None:
        uname = payload.username.strip()
        if uname and uname != teacher.username:
            existing = db.query(User).filter(User.username == uname, User.id != teacher.id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Username '{uname}' already taken.")
            teacher.username = uname

    if payload.email is not None:
        em = payload.email.strip().lower()
        if em and em != teacher.email:
            existing = db.query(User).filter(User.email == em, User.id != teacher.id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Email '{em}' is already registered.")
            teacher.email = em

    if payload.full_name is not None and payload.full_name.strip():
        teacher.full_name = payload.full_name.strip()

    if payload.department is not None:
        teacher.department = payload.department.strip()

    if payload.is_active is not None:
        teacher.is_active = bool(payload.is_active)

    if payload.password is not None and payload.password.strip():
        pwd = payload.password.strip()
        if len(pwd) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        teacher.hashed_password = hash_password(pwd)

    # If assignments list provided, synchronize assignments
    if payload.assignments is not None:
        db.query(ClassSubject).filter(ClassSubject.teacher_id == teacher.id).delete()
        for assign in payload.assignments:
            cls = db.query(Class).filter(Class.id == assign.class_id).first()
            subj = db.query(Subject).filter(Subject.id == assign.subject_id).first()
            if not cls or not subj:
                continue
            existing_cs = db.query(ClassSubject).filter(
                ClassSubject.class_id == assign.class_id,
                ClassSubject.subject_id == assign.subject_id,
                ClassSubject.teacher_id == teacher.id,
            ).first()
            if not existing_cs:
                cs = ClassSubject(
                    class_id=assign.class_id,
                    subject_id=assign.subject_id,
                    teacher_id=teacher.id,
                )
                db.add(cs)

    db.commit()
    db.refresh(teacher)
    return format_subject_teacher_detail(teacher, db)


@router.patch("/class-teacher/subject-teachers/{teacher_identifier}/toggle-status", response_model=SubjectTeacherDetailResponse)
def toggle_subject_teacher_status(
    teacher_identifier: str,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Toggle active / deactivated status of a Subject Teacher."""
    teacher = _find_subject_teacher(teacher_identifier, db)
    teacher.is_active = not bool(teacher.is_active)
    db.commit()
    db.refresh(teacher)
    return format_subject_teacher_detail(teacher, db)


@router.post("/class-teacher/subject-teachers/{teacher_identifier}/assignments", response_model=SubjectTeacherDetailResponse)
def assign_subject_teacher_to_class(
    teacher_identifier: str,
    assignment: TeacherAssignmentInput,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Assign a Subject Teacher to a specific subject in a class."""
    teacher = _find_subject_teacher(teacher_identifier, db)
    cls = db.query(Class).filter(Class.id == assignment.class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")
    subj = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")

    existing_cs = db.query(ClassSubject).filter(
        ClassSubject.class_id == assignment.class_id,
        ClassSubject.subject_id == assignment.subject_id,
        ClassSubject.teacher_id == teacher.id,
    ).first()
    if existing_cs:
        raise HTTPException(status_code=400, detail="This assignment already exists.")

    cs = ClassSubject(
        class_id=assignment.class_id,
        subject_id=assignment.subject_id,
        teacher_id=teacher.id,
    )
    db.add(cs)
    db.commit()
    db.refresh(teacher)
    return format_subject_teacher_detail(teacher, db)


@router.delete("/class-teacher/subject-teachers/{teacher_identifier}/assignments/{assignment_id}", response_model=SubjectTeacherDetailResponse)
def remove_subject_teacher_assignment(
    teacher_identifier: str,
    assignment_id: int,
    current_teacher: User = Depends(require_class_teacher),
    db: Session = Depends(get_db),
):
    """Remove a specific subject-class assignment from a Subject Teacher."""
    teacher = _find_subject_teacher(teacher_identifier, db)
    cs = db.query(ClassSubject).filter(
        ClassSubject.id == assignment_id,
        ClassSubject.teacher_id == teacher.id,
    ).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    db.delete(cs)
    db.commit()
    db.refresh(teacher)
    return format_subject_teacher_detail(teacher, db)


@router.get("/subject-teacher/classes")
def get_subject_teacher_classes(
    current_teacher: User = Depends(require_subject_teacher),
    db: Session = Depends(get_db),
):
    """
    Classes and subjects assigned to subject teacher.
    Protected: Accessible by SUBJECT_TEACHER, CLASS_TEACHER, or ADMIN.
    """
    # Query assignments for this teacher from ClassSubject table
    query = (
        db.query(ClassSubject)
        .join(Class, Class.id == ClassSubject.class_id)
        .join(Subject, Subject.id == ClassSubject.subject_id)
    )

    if current_teacher.role == UserRole.ADMIN:
        assignments = query.all()
    elif current_teacher.role == UserRole.CLASS_TEACHER:
        # Class teacher sees subjects they teach directly plus subjects for their mentored section
        mentored_class = db.query(Class).filter(Class.class_teacher_id == current_teacher.id).first()
        mentored_class_id = mentored_class.id if mentored_class else -1
        assignments = query.filter(
            (ClassSubject.teacher_id == current_teacher.id) |
            (ClassSubject.class_id == mentored_class_id)
        ).all()
    else:
        # Subject teacher strictly sees only assigned courses
        assignments = query.filter(ClassSubject.teacher_id == current_teacher.id).all()

    assigned_subjects = []
    classes_map = {}
    subjects_map = {}

    for cs in assignments:
        c = cs.class_group
        s = cs.subject
        if c and s:
            assigned_subjects.append({
                "id": cs.id,
                "class_id": cs.class_id,
                "class_name": c.name,
                "department": c.department,
                "year": c.year,
                "section": c.section,
                "subject_id": cs.subject_id,
                "subject_name": s.name,
                "subject_code": s.code,
                "code": s.code,
                "class": c.name,
                "name": f"{s.name} ({s.code})",
            })
            classes_map[c.id] = {
                "id": c.id,
                "name": c.name,
                "department": c.department,
                "year": c.year,
                "section": c.section,
            }
            subjects_map[s.id] = {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "department": s.department,
            }

    if current_teacher.role == UserRole.ADMIN:
        all_classes_objs = db.query(Class).all()
        all_subjects_objs = db.query(Subject).all()
        available_classes = [
            {"id": c.id, "name": c.name, "department": c.department, "year": c.year, "section": c.section}
            for c in all_classes_objs
        ]
        available_subjects = [
            {"id": s.id, "name": s.name, "code": s.code, "department": s.department}
            for s in all_subjects_objs
        ]
        # Only if institution database has zero ClassSubject links at all, provide bootstrap view for admin
        if not assigned_subjects and all_classes_objs and all_subjects_objs:
            for s in all_subjects_objs:
                assigned_subjects.append({
                    "id": s.id,
                    "class_id": all_classes_objs[0].id,
                    "class_name": all_classes_objs[0].name,
                    "department": all_classes_objs[0].department,
                    "year": all_classes_objs[0].year,
                    "section": all_classes_objs[0].section,
                    "subject_id": s.id,
                    "subject_name": s.name,
                    "subject_code": s.code,
                    "class": all_classes_objs[0].name,
                    "name": f"{s.name} ({s.code})",
                })
    else:
        available_classes = list(classes_map.values())
        available_subjects = list(subjects_map.values())

    return {
        "portal": "Subject Teacher Portal",
        "teacher_name": current_teacher.full_name,
        "teacher_id": current_teacher.id,
        "role": current_teacher.role.value if hasattr(current_teacher.role, "value") else str(current_teacher.role),
        "assigned_subjects": assigned_subjects,
        "assigned_classes": list(classes_map.values()),
        "available_classes": available_classes,
        "available_subjects": available_subjects,
    }



@router.get("/", response_model=List[UserResponse])
def list_teachers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all faculty/teachers."""
    return db.query(User).all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new faculty account (Admin only)."""
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username or email already exists.",
        )

    new_teacher = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        department=user_in.department,
    )
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    return new_teacher


@router.get("/{teacher_id}", response_model=UserResponse)
def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single teacher details."""
    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return t


@router.put("/{teacher_id}", response_model=UserResponse)
def update_teacher(
    teacher_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update teacher details (Admin only)."""
    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    if user_update.email is not None and user_update.email != t.email:
        existing = db.query(User).filter(User.email == user_update.email, User.id != teacher_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered to another user.")
        t.email = user_update.email

    if user_update.full_name is not None:
        t.full_name = user_update.full_name
    if user_update.role is not None:
        t.role = user_update.role
    if user_update.department is not None:
        t.department = user_update.department
    if user_update.password is not None and user_update.password.strip():
        t.hashed_password = hash_password(user_update.password)

    db.commit()
    db.refresh(t)
    return t


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a teacher account (Admin only)."""
    if teacher_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")

    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    db.delete(t)
    db.commit()
    return None
