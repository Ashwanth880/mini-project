from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.academic import Subject
from app.schemas.academic import SubjectCreate, SubjectUpdate, SubjectResponse
from app.api.deps import require_admin, get_current_user

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("/", response_model=List[SubjectResponse])
def list_subjects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all subjects."""
    return db.query(Subject).all()


@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    subj_in: SubjectCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new subject (Admin only)."""
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


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get subject by ID."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return s


@router.put("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    subj_update: SubjectUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update subject (Admin only)."""
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


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete subject (Admin only)."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")
    db.delete(s)
    db.commit()
    return None
