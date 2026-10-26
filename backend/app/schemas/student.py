from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class StudentBase(BaseModel):
    roll_number: str
    register_number: str
    full_name: str
    department: str
    year: int
    section: str
    class_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    roll_number: Optional[str] = None
    register_number: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    section: Optional[str] = None
    class_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class StudentResponse(StudentBase):
    id: int
    is_active: bool = True
    face_enrolled: bool
    class_name: Optional[str] = None
    face_image_path: Optional[str] = None
    attendance_rate: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaceEnrollmentResponse(BaseModel):
    success: bool = True
    message: str = "Face enrolled successfully"
    detail: Optional[str] = "Face enrolled successfully"
    student_id: int
    roll_number: str
    full_name: str
    face_enrolled: bool = True
    face_image_path: Optional[str] = None
    embedding_dimension: Optional[int] = None
    face_confidence: Optional[float] = None
    quality_metrics: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class StudentFaceStatusResponse(BaseModel):
    student_id: int
    roll_number: str
    full_name: str
    face_enrolled: bool
    face_image_path: Optional[str] = None
    embedding_dimension: Optional[int] = None
    enrolled_at: Optional[datetime] = None
    status_label: str

    model_config = ConfigDict(from_attributes=True)


class ClassTeacherStudentCreate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    roll_number: str
    register_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ClassTeacherStudentUpdate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    roll_number: Optional[str] = None
    register_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

