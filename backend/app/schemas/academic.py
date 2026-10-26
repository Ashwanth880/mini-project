from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ClassBase(BaseModel):
    name: str
    department: str
    year: int
    section: str
    class_teacher_id: Optional[int] = None


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    section: Optional[str] = None
    class_teacher_id: Optional[int] = None


class AssignClassTeacherRequest(BaseModel):
    class_teacher_id: int


class ClassResponse(ClassBase):
    id: int
    class_teacher_name: Optional[str] = None
    student_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectBase(BaseModel):
    code: str
    name: str
    department: str


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None


class SubjectResponse(SubjectBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassSubjectCreate(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: int


class ClassSubjectResponse(ClassSubjectCreate):
    id: int
    class_name: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
