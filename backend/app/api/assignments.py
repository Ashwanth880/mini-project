from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.academic import Class, Subject, ClassSubject
from app.schemas.academic import ClassSubjectCreate, ClassSubjectResponse
from app.api.deps import require_admin, get_current_user

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.get("/", response_model=List[ClassSubjectResponse])
def list_assignments(
    class_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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


@router.post("/", response_model=ClassSubjectResponse, status_code=status.HTTP_201_CREATED)
def assign_subject_teacher(
    assign_in: ClassSubjectCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign a subject teacher to teach a subject to a specific class (Admin only)."""
    c = db.query(Class).filter(Class.id == assign_in.class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found.")

    s = db.query(Subject).filter(Subject.id == assign_in.subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    t = db.query(User).filter(User.id == assign_in.teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")

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


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Remove a subject teacher assignment (Admin only)."""
    item = db.query(ClassSubject).filter(ClassSubject.id == assignment_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    db.delete(item)
    db.commit()
    return None
