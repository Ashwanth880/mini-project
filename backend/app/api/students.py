import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, StudentFace
from app.models.academic import Class, ClassSubject
from app.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    FaceEnrollmentResponse,
    StudentFaceStatusResponse,
)
from app.api.deps import require_admin, get_current_user, get_optional_current_user
from app.services.face_service import (
    face_service,
    StudentNotFoundError,
    NoFaceDetectedError,
    MultipleFacesDetectedError,
    ImageQualityError,
    InvalidImageError,
    FaceEnrollmentError,
)

logger = logging.getLogger("one-click-attendance.api.students")

router = APIRouter(prefix="/students", tags=["Students"])


def format_student_response(st: Student) -> StudentResponse:
    primary_face = next((f for f in st.faces if f.is_primary), None) if st.faces else None
    if not primary_face and st.faces:
        primary_face = st.faces[0]
    face_img = primary_face.image_path if primary_face else None

    att_rate = None
    if st.attendances:
        present_count = sum(1 for a in st.attendances if a.status.value == "PRESENT")
        att_rate = round((present_count / len(st.attendances)) * 100.0, 1)

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
        email=st.email,
        phone=st.phone,
        is_active=st.is_active,
        face_enrolled=st.face_enrolled,
        face_image_path=face_img,
        attendance_rate=att_rate,
        created_at=st.created_at,
    )


@router.get("/", response_model=List[StudentResponse])
def list_students(
    class_id: Optional[int] = None,
    department: Optional[str] = None,
    year: Optional[int] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve enrolled students with optional filters scoped to teacher role permissions."""
    query = db.query(Student)

    # Enforce role boundaries: non-admin faculty can only view students in sections they mentor or teach
    if current_user.role == UserRole.CLASS_TEACHER:
        teacher_class = db.query(Class).filter(Class.class_teacher_id == current_user.id).first()
        if teacher_class:
            query = query.filter(Student.class_id == teacher_class.id)
    elif current_user.role == UserRole.SUBJECT_TEACHER:
        assigned_cs = db.query(ClassSubject).filter(ClassSubject.teacher_id == current_user.id).all()
        assigned_class_ids = [cs.class_id for cs in assigned_cs]
        query = query.filter(Student.class_id.in_(assigned_class_ids))

    if class_id:
        query = query.filter(Student.class_id == class_id)
    if department:
        query = query.filter(Student.department == department)
    if year:
        query = query.filter(Student.year == year)
    if section:
        query = query.filter(Student.section == section)

    students = query.order_by(Student.roll_number.asc()).all()
    return [format_student_response(st) for st in students]


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Register a new student (Admin only)."""
    existing = db.query(Student).filter(
        (Student.roll_number == student_in.roll_number) |
        (Student.register_number == student_in.register_number)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student with this roll number or register number already exists.",
        )

    class_id = student_in.class_id
    if not class_id:
        matched_class = db.query(Class).filter(
            Class.department == student_in.department,
            Class.year == student_in.year,
            Class.section == student_in.section,
        ).first()
        if matched_class:
            class_id = matched_class.id

    new_student = Student(
        roll_number=student_in.roll_number,
        register_number=student_in.register_number,
        full_name=student_in.full_name,
        department=student_in.department,
        year=student_in.year,
        section=student_in.section,
        class_id=class_id,
        email=student_in.email,
        phone=student_in.phone,
        is_active=True,
        face_enrolled=False,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return format_student_response(new_student)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a specific student with role-based access validation."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    if current_user.role == UserRole.CLASS_TEACHER:
        teacher_class = db.query(Class).filter(Class.class_teacher_id == current_user.id).first()
        if not teacher_class or st.class_id != teacher_class.id:
            raise HTTPException(status_code=403, detail="Not authorized to access student from another class.")
    elif current_user.role == UserRole.SUBJECT_TEACHER:
        is_assigned = db.query(ClassSubject).filter(
            ClassSubject.teacher_id == current_user.id,
            ClassSubject.class_id == st.class_id,
        ).first()
        if not is_assigned:
            raise HTTPException(status_code=403, detail="Not authorized to access student details outside assigned classes.")

    return format_student_response(st)


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    student_update: StudentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update student attributes or assign to a class (Admin only)."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    update_data = student_update.model_dump(exclude_unset=True)

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

    return format_student_response(st)


@router.patch("/{student_id}/toggle-status", response_model=StudentResponse)
def toggle_student_status(
    student_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Toggle student active/inactive status (Admin only)."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    st.is_active = not st.is_active
    db.commit()
    db.refresh(st)
    return format_student_response(st)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a student and associated records (Admin only)."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    db.delete(st)
    db.commit()
    return None


@router.post("/{student_id}/face", response_model=FaceEnrollmentResponse, status_code=status.HTTP_200_OK)
def enroll_student_face_api(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enroll student face photograph via Computer Vision pipeline:
    1. Receive image file.
    2. Validate file format, size, and raster integrity.
    3. Detect faces using OpenCV YuNet.
    4. Require exactly one usable face (reject 0 faces, reject >1 faces).
    5. Perform basic image quality checks (sharpness, lighting, resolution).
    6. Generate a 128D face embedding using OpenCV SFace.
    7. Store the embedding strictly associated with the verified student.
    8. Store the original image securely in data/faces.
    """
    logger.info(f"POST /students/{student_id}/face invoked: filename='{file.filename}', content_type='{file.content_type}'")

    # 1. Verify student exists in the database
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        logger.warning(f"Face enrollment rejected: Student ID {student_id} not found.")
        raise HTTPException(status_code=404, detail="Student not found")

    # Enforce role boundary: Class teachers can only enroll students in their assigned section
    if current_user.role == UserRole.CLASS_TEACHER:
        teacher_class = db.query(Class).filter(Class.class_teacher_id == current_user.id).first()
        if not teacher_class or student.class_id != teacher_class.id:
            logger.warning(
                f"Class teacher '{current_user.username}' attempted unauthorized face enrollment for student {student_id}"
            )
            raise HTTPException(status_code=403, detail="Not authorized to enroll face for a student in another class.")
    elif current_user.role == UserRole.SUBJECT_TEACHER:
        raise HTTPException(status_code=403, detail="Subject teachers are not authorized to enroll student faces.")

    # 2. Read image content
    try:
        content = file.file.read()
    except Exception as exc:
        logger.error(f"Failed to read uploaded file: {exc}")
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(exc)}")

    # 3-10. Execute face enrollment through FaceService
    try:
        result = face_service.enroll_student_face(
            db=db,
            student_id=student.id,
            image_bytes=content,
            filename=file.filename or "portrait.jpg",
            content_type=file.content_type,
        )
        return FaceEnrollmentResponse(**result)
    except StudentNotFoundError:
        raise HTTPException(status_code=404, detail="Student not found")
    except NoFaceDetectedError:
        raise HTTPException(status_code=400, detail="No face detected")
    except MultipleFacesDetectedError:
        raise HTTPException(status_code=400, detail="Multiple faces detected")
    except ImageQualityError as exc:
        logger.warning(f"Image quality check failed: {exc}")
        raise HTTPException(status_code=400, detail="Image quality insufficient")
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(exc)}")
    except FaceEnrollmentError as exc:
        logger.error(f"Internal face enrollment error: {exc}")
        raise HTTPException(status_code=500, detail="Face enrollment failed")


@router.get("/{student_id}/face", response_model=StudentFaceStatusResponse)
def get_student_face_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View face enrollment status, embedding dimension, and stored portrait for a student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role == UserRole.CLASS_TEACHER:
        teacher_class = db.query(Class).filter(Class.class_teacher_id == current_user.id).first()
        if not teacher_class or student.class_id != teacher_class.id:
            raise HTTPException(status_code=403, detail="Not authorized for this student.")
    elif current_user.role == UserRole.SUBJECT_TEACHER:
        is_assigned = db.query(ClassSubject).filter(
            ClassSubject.teacher_id == current_user.id,
            ClassSubject.class_id == student.class_id,
        ).first()
        if not is_assigned:
            raise HTTPException(status_code=403, detail="Not authorized to view biometric data for students outside assigned classes.")

    face = db.query(StudentFace).filter(
        StudentFace.student_id == student.id,
        StudentFace.is_primary == True
    ).first()

    embedding_dims = None
    if face and face.embedding:
        try:
            vec = json.loads(face.embedding)
            embedding_dims = len(vec)
        except Exception:
            pass

    return StudentFaceStatusResponse(
        student_id=student.id,
        roll_number=student.roll_number,
        full_name=student.full_name,
        face_enrolled=student.face_enrolled,
        face_image_path=face.image_path if face else None,
        embedding_dimension=embedding_dims,
        enrolled_at=face.created_at if face else None,
        status_label="Enrolled" if student.face_enrolled else "Pending Enrollment",
    )


@router.post("/{student_id}/enroll-face", response_model=FaceEnrollmentResponse)
def enroll_student_face(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll student face photograph (alias to /students/{student_id}/face)."""
    return enroll_student_face_api(student_id=student_id, file=file, db=db, current_user=current_user)

