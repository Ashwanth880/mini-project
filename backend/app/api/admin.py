from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.academic import Class, Subject, ClassSubject
from app.models.attendance import Attendance, AttendanceImage, AttendanceStatus
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.academic import (
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    AssignClassTeacherRequest,
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    ClassSubjectCreate,
    ClassSubjectResponse,
)
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse
from app.schemas.attendance import AttendanceRecordCreate, AttendanceRecordResponse
from app.utils.security import hash_password
from app.api.deps import require_admin

router = APIRouter(prefix="/admin", tags=["Admin Portal"], dependencies=[Depends(require_admin)])


# -------------------------------------------------------------
# 1. Dashboard Metrics
# -------------------------------------------------------------
@router.get("/dashboard-stats")
def get_admin_dashboard_stats(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Overall institution and system summary metrics."""
    total_teachers = db.query(User).count()
    total_students = db.query(Student).count()
    enrolled_faces = db.query(Student).filter(Student.face_enrolled.is_(True)).count()
    total_classes = db.query(Class).count()
    total_subjects = db.query(Subject).count()
    total_attendance_records = db.query(Attendance).count()
    total_attendance_images = db.query(AttendanceImage).count()

    present_count = db.query(Attendance).filter(Attendance.status == AttendanceStatus.PRESENT).count()
    attendance_rate = round((present_count / total_attendance_records * 100), 1) if total_attendance_records > 0 else 0.0

    return {
        "admin_user": current_admin.full_name,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "enrolled_faces": enrolled_faces,
        "total_classes": total_classes,
        "total_subjects": total_subjects,
        "total_attendance_records": total_attendance_records,
        "total_attendance_images": total_attendance_images,
        "attendance_rate": attendance_rate,
        "status": "active",
    }


# -------------------------------------------------------------
# 2. Classes Management
# -------------------------------------------------------------
@router.get("/classes", response_model=List[ClassResponse])
def list_classes(db: Session = Depends(get_db)):
    """List all registered academic classes with teacher info and student count."""
    classes = db.query(Class).all()
    results = []
    for c in classes:
        res = ClassResponse(
            id=c.id,
            name=c.name,
            department=c.department,
            year=c.year,
            section=c.section,
            class_teacher_id=c.class_teacher_id,
            class_teacher_name=c.class_teacher.full_name if c.class_teacher else None,
            student_count=len(c.students),
            created_at=c.created_at,
        )
        results.append(res)
    return results


@router.post("/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(class_in: ClassCreate, db: Session = Depends(get_db)):
    """Create a new academic class (e.g. Computer Science - Year 3 - Sec A)."""
    # Check if a class with duplicate dept/year/section exists
    existing = db.query(Class).filter(
        Class.department == class_in.department,
        Class.year == class_in.year,
        Class.section == class_in.section,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Class for {class_in.department} Year {class_in.year} Section {class_in.section} already exists.",
        )

    # Check if name is unique
    existing_name = db.query(Class).filter(Class.name == class_in.name).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Class with name '{class_in.name}' already exists.",
        )

    teacher_name = None
    if class_in.class_teacher_id:
        teacher = db.query(User).filter(User.id == class_in.class_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Assigned class teacher not found.")
        teacher_name = teacher.full_name

    new_class = Class(
        name=class_in.name,
        department=class_in.department,
        year=class_in.year,
        section=class_in.section,
        class_teacher_id=class_in.class_teacher_id,
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)

    return ClassResponse(
        id=new_class.id,
        name=new_class.name,
        department=new_class.department,
        year=new_class.year,
        section=new_class.section,
        class_teacher_id=new_class.class_teacher_id,
        class_teacher_name=teacher_name,
        student_count=0,
        created_at=new_class.created_at,
    )


@router.get("/classes/{class_id}", response_model=ClassResponse)
def get_class(class_id: int, db: Session = Depends(get_db)):
    """Retrieve details of a specific class."""
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")
    return ClassResponse(
        id=c.id,
        name=c.name,
        department=c.department,
        year=c.year,
        section=c.section,
        class_teacher_id=c.class_teacher_id,
        class_teacher_name=c.class_teacher.full_name if c.class_teacher else None,
        student_count=len(c.students),
        created_at=c.created_at,
    )


@router.put("/classes/{class_id}", response_model=ClassResponse)
def update_class(
    class_id: int,
    class_update: ClassUpdate,
    db: Session = Depends(get_db),
):
    """Update class attributes."""
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")

    if class_update.name is not None and class_update.name != c.name:
        existing = db.query(Class).filter(Class.name == class_update.name, Class.id != class_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Class name already in use.")
        c.name = class_update.name

    if class_update.department is not None:
        c.department = class_update.department
    if class_update.year is not None:
        c.year = class_update.year
    if class_update.section is not None:
        c.section = class_update.section

    if class_update.class_teacher_id is not None:
        if class_update.class_teacher_id == 0:
            c.class_teacher_id = None
        else:
            teacher = db.query(User).filter(User.id == class_update.class_teacher_id).first()
            if not teacher:
                raise HTTPException(status_code=404, detail="Teacher not found.")
            c.class_teacher_id = teacher.id

    db.commit()
    db.refresh(c)

    return ClassResponse(
        id=c.id,
        name=c.name,
        department=c.department,
        year=c.year,
        section=c.section,
        class_teacher_id=c.class_teacher_id,
        class_teacher_name=c.class_teacher.full_name if c.class_teacher else None,
        student_count=len(c.students),
        created_at=c.created_at,
    )


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: Session = Depends(get_db)):
    """Delete a class and associated records."""
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")
    db.delete(c)
    db.commit()
    return None


@router.put("/classes/{class_id}/assign-teacher", response_model=ClassResponse)
def assign_class_teacher(
    class_id: int,
    req: AssignClassTeacherRequest,
    db: Session = Depends(get_db),
):
    """Assign or reassign a mentor/Class Teacher to a specific class."""
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")

    teacher = db.query(User).filter(User.id == req.class_teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    c.class_teacher_id = teacher.id
    db.commit()
    db.refresh(c)

    return ClassResponse(
        id=c.id,
        name=c.name,
        department=c.department,
        year=c.year,
        section=c.section,
        class_teacher_id=c.class_teacher_id,
        class_teacher_name=teacher.full_name,
        student_count=len(c.students),
        created_at=c.created_at,
    )


# -------------------------------------------------------------
# 3. Subjects Management
# -------------------------------------------------------------
@router.get("/subjects", response_model=List[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    """List all subjects offered in the curriculum."""
    return db.query(Subject).all()


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(subj_in: SubjectCreate, db: Session = Depends(get_db)):
    """Register a new subject with course code."""
    existing = db.query(Subject).filter(Subject.code == subj_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject with code '{subj_in.code}' already exists.",
        )

    new_subj = Subject(
        code=subj_in.code,
        name=subj_in.name,
        department=subj_in.department,
    )
    db.add(new_subj)
    db.commit()
    db.refresh(new_subj)
    return new_subj


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    """Get subject by ID."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return s


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    subj_update: SubjectUpdate,
    db: Session = Depends(get_db),
):
    """Update subject information."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    if subj_update.code is not None and subj_update.code != s.code:
        existing = db.query(Subject).filter(Subject.code == subj_update.code, Subject.id != subject_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Subject code already in use.")
        s.code = subj_update.code

    if subj_update.name is not None:
        s.name = subj_update.name
    if subj_update.department is not None:
        s.department = subj_update.department

    db.commit()
    db.refresh(s)
    return s


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    """Delete a subject."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")
    db.delete(s)
    db.commit()
    return None


# -------------------------------------------------------------
# 4. Teachers Management
# -------------------------------------------------------------
@router.get("/teachers", response_model=List[UserResponse])
def list_teachers(db: Session = Depends(get_db)):
    """List all teachers and faculty members."""
    return db.query(User).all()


@router.post("/teachers", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new faculty account with hashed password."""
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


@router.get("/teachers/{teacher_id}", response_model=UserResponse)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """Get single teacher details."""
    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return t


@router.put("/teachers/{teacher_id}", response_model=UserResponse)
def update_teacher(
    teacher_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
):
    """Update teacher details (role, email, department, password)."""
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


@router.delete("/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a teacher account."""
    if teacher_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")

    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    db.delete(t)
    db.commit()
    return None


# -------------------------------------------------------------
# 5. Subject Teacher Assignments (ClassSubject)
# -------------------------------------------------------------
@router.get("/assignments", response_model=List[ClassSubjectResponse])
def list_assignments(
    class_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List all mappings between Classes, Subjects, and assigned Teachers."""
    query = db.query(ClassSubject)
    if class_id:
        query = query.filter(ClassSubject.class_id == class_id)
    if teacher_id:
        query = query.filter(ClassSubject.teacher_id == teacher_id)

    items = query.all()
    results = []
    for item in items:
        res = ClassSubjectResponse(
            id=item.id,
            class_id=item.class_id,
            subject_id=item.subject_id,
            teacher_id=item.teacher_id,
            class_name=item.class_group.name if item.class_group else None,
            subject_code=item.subject.code if item.subject else None,
            subject_name=item.subject.name if item.subject else None,
            teacher_name=item.teacher.full_name if item.teacher else None,
            created_at=item.created_at,
        )
        results.append(res)
    return results


@router.post("/assignments", response_model=ClassSubjectResponse, status_code=status.HTTP_201_CREATED)
def assign_subject_teacher(
    assign_in: ClassSubjectCreate,
    db: Session = Depends(get_db),
):
    """Assign a subject teacher to teach a subject to a specific class."""
    c = db.query(Class).filter(Class.id == assign_in.class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")

    s = db.query(Subject).filter(Subject.id == assign_in.subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    t = db.query(User).filter(User.id == assign_in.teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    # Check for existing duplicate mapping
    existing = db.query(ClassSubject).filter(
        ClassSubject.class_id == assign_in.class_id,
        ClassSubject.subject_id == assign_in.subject_id,
        ClassSubject.teacher_id == assign_in.teacher_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment already exists.",
        )

    assignment = ClassSubject(
        class_id=assign_in.class_id,
        subject_id=assign_in.subject_id,
        teacher_id=assign_in.teacher_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return ClassSubjectResponse(
        id=assignment.id,
        class_id=assignment.class_id,
        subject_id=assignment.subject_id,
        teacher_id=assignment.teacher_id,
        class_name=c.name,
        subject_code=s.code,
        subject_name=s.name,
        teacher_name=t.full_name,
        created_at=assignment.created_at,
    )


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """Remove a subject teacher assignment."""
    item = db.query(ClassSubject).filter(ClassSubject.id == assignment_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    db.delete(item)
    db.commit()
    return None


# -------------------------------------------------------------
# 6. Students Management
# -------------------------------------------------------------
@router.get("/students", response_model=List[StudentResponse])
def list_admin_students(
    class_id: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all students with optional class or department filtering."""
    query = db.query(Student)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if department:
        query = query.filter(Student.department == department)

    students = query.order_by(Student.roll_number.asc()).all()
    results = []
    for st in students:
        res = StudentResponse(
            id=st.id,
            roll_number=st.roll_number,
            register_number=st.register_number,
            full_name=st.full_name,
            department=st.department,
            year=st.year,
            section=st.section,
            class_id=st.class_id,
            class_name=st.class_group.name if st.class_group else None,
            is_active=st.is_active,
            face_enrolled=st.face_enrolled,
            created_at=st.created_at,
        )
        results.append(res)
    return results


@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_admin_student(student_in: StudentCreate, db: Session = Depends(get_db)):
    """Register a new student and associate with a class."""
    existing = db.query(Student).filter(
        (Student.roll_number == student_in.roll_number) |
        (Student.register_number == student_in.register_number)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student with this roll number or register number already exists.",
        )

    # Automatically resolve class_id if not explicitly provided
    class_id = student_in.class_id
    class_name = None
    if not class_id:
        matched_class = db.query(Class).filter(
            Class.department == student_in.department,
            Class.year == student_in.year,
            Class.section == student_in.section,
        ).first()
        if matched_class:
            class_id = matched_class.id
            class_name = matched_class.name
    else:
        c = db.query(Class).filter(Class.id == class_id).first()
        if c:
            class_name = c.name

    new_student = Student(
        roll_number=student_in.roll_number,
        register_number=student_in.register_number,
        full_name=student_in.full_name,
        department=student_in.department,
        year=student_in.year,
        section=student_in.section,
        class_id=class_id,
        is_active=True,
        face_enrolled=False,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return StudentResponse(
        id=new_student.id,
        roll_number=new_student.roll_number,
        register_number=new_student.register_number,
        full_name=new_student.full_name,
        department=new_student.department,
        year=new_student.year,
        section=new_student.section,
        class_id=new_student.class_id,
        class_name=class_name,
        is_active=new_student.is_active,
        face_enrolled=new_student.face_enrolled,
        created_at=new_student.created_at,
    )


@router.get("/students/{student_id}", response_model=StudentResponse)
def get_admin_student(student_id: int, db: Session = Depends(get_db)):
    """Retrieve details of a specific student."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    return StudentResponse(
        id=st.id,
        roll_number=st.roll_number,
        register_number=st.register_number,
        full_name=st.full_name,
        department=st.department,
        year=st.year,
        section=st.section,
        class_id=st.class_id,
        class_name=st.class_group.name if st.class_group else None,
        is_active=st.is_active,
        face_enrolled=st.face_enrolled,
        created_at=st.created_at,
    )


@router.put("/students/{student_id}", response_model=StudentResponse)
def update_admin_student(
    student_id: int,
    student_update: StudentUpdate,
    db: Session = Depends(get_db),
):
    """Update student attributes or assign/reassign to a different class."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    update_data = student_update.model_dump(exclude_unset=True)

    # Validate uniqueness if roll_number or register_number are changing
    if "roll_number" in update_data and update_data["roll_number"] != st.roll_number:
        exists = db.query(Student).filter(Student.roll_number == update_data["roll_number"], Student.id != student_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Roll number already exists.")
    if "register_number" in update_data and update_data["register_number"] != st.register_number:
        exists = db.query(Student).filter(Student.register_number == update_data["register_number"], Student.id != student_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Register number already exists.")

    for field, val in update_data.items():
        setattr(st, field, val)

    db.commit()
    db.refresh(st)

    return StudentResponse(
        id=st.id,
        roll_number=st.roll_number,
        register_number=st.register_number,
        full_name=st.full_name,
        department=st.department,
        year=st.year,
        section=st.section,
        class_id=st.class_id,
        class_name=st.class_group.name if st.class_group else None,
        is_active=st.is_active,
        face_enrolled=st.face_enrolled,
        created_at=st.created_at,
    )


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_student(student_id: int, db: Session = Depends(get_db)):
    """Delete a student and associated attendance and face records."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    db.delete(st)
    db.commit()
    return None


# -------------------------------------------------------------
# 7. Attendance Records View & Management
# -------------------------------------------------------------
@router.get("/attendance", response_model=List[AttendanceRecordResponse])
def view_attendance_records(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    date_val: Optional[date] = None,
    status_filter: Optional[AttendanceStatus] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """View institution-wide attendance records with multi-criteria filters."""
    query = db.query(Attendance)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if date_val:
        query = query.filter(Attendance.date == date_val)
    if status_filter:
        query = query.filter(Attendance.status == status_filter)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)

    records = query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()
    results = []
    for r in records:
        res = AttendanceRecordResponse(
            id=r.id,
            student_id=r.student_id,
            class_id=r.class_id,
            subject_id=r.subject_id,
            teacher_id=r.teacher_id,
            date=r.date,
            period=r.period,
            status=r.status,
            confidence=r.confidence,
            attendance_image_id=r.attendance_image_id,
            bounding_box=r.bounding_box,
            is_manual=r.is_manual,
            student_roll=r.student.roll_number if r.student else None,
            student_name=r.student.full_name if r.student else None,
            created_at=r.created_at,
        )
        results.append(res)
    return results


@router.post("/attendance", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
def create_attendance_record(
    record_in: AttendanceRecordCreate,
    db: Session = Depends(get_db),
):
    """Create a manual attendance record."""
    student = db.query(Student).filter(Student.id == record_in.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    class_obj = db.query(Class).filter(Class.id == record_in.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found.")

    subject_obj = db.query(Subject).filter(Subject.id == record_in.subject_id).first()
    if not subject_obj:
        raise HTTPException(status_code=404, detail="Subject not found.")

    new_record = Attendance(
        student_id=record_in.student_id,
        class_id=record_in.class_id,
        subject_id=record_in.subject_id,
        teacher_id=record_in.teacher_id,
        date=record_in.date,
        period=record_in.period,
        status=record_in.status,
        confidence=record_in.confidence,
        attendance_image_id=record_in.attendance_image_id,
        bounding_box=record_in.bounding_box,
        is_manual=True,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return AttendanceRecordResponse(
        id=new_record.id,
        student_id=new_record.student_id,
        class_id=new_record.class_id,
        subject_id=new_record.subject_id,
        teacher_id=new_record.teacher_id,
        date=new_record.date,
        period=new_record.period,
        status=new_record.status,
        confidence=new_record.confidence,
        attendance_image_id=new_record.attendance_image_id,
        bounding_box=new_record.bounding_box,
        is_manual=new_record.is_manual,
        student_roll=student.roll_number,
        student_name=student.full_name,
        created_at=new_record.created_at,
    )


@router.delete("/attendance/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance_record(record_id: int, db: Session = Depends(get_db)):
    """Delete an attendance record."""
    rec = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    db.delete(rec)
    db.commit()
    return None
