from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.academic import Class
from app.schemas.academic import (
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    AssignClassTeacherRequest,
)
from app.api.deps import require_admin, get_current_user

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.get("/", response_model=List[ClassResponse])
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    class_in: ClassCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new academic class (Admin only)."""
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


@router.get("/{class_id}", response_model=ClassResponse)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single class details."""
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


@router.put("/{class_id}", response_model=ClassResponse)
def update_class(
    class_id: int,
    class_update: ClassUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update class information (Admin only)."""
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


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete class (Admin only)."""
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")
    db.delete(c)
    db.commit()
    return None


@router.put("/{class_id}/assign-teacher", response_model=ClassResponse)
def assign_class_teacher(
    class_id: int,
    req: AssignClassTeacherRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign or reassign class teacher (Admin only)."""
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
