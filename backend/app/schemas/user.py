from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from app.models.user import UserRole


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.SUBJECT_TEACHER
    department: Optional[str] = None
    teacher_id: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    teacher_id: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    username: str  # Can be username, email, or teacher_id
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# SUBJECT TEACHER MANAGEMENT SCHEMAS (CLASS TEACHER PORTAL)
# ===========================================================================

class TeacherAssignmentInput(BaseModel):
    class_id: int
    subject_id: int


class SubjectTeacherCreate(BaseModel):
    full_name: Optional[str] = None
    name: Optional[str] = None
    teacher_id: str  # Unique Teacher ID (e.g. T101)
    username: str    # Unique username
    password: str    # At least 6 characters
    email: Optional[str] = None  # If omitted, auto-generated
    department: Optional[str] = None
    assignments: Optional[List[TeacherAssignmentInput]] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data):
        if isinstance(data, dict):
            if not data.get("full_name") and data.get("name"):
                data["full_name"] = data["name"]
        return data


class SubjectTeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    name: Optional[str] = None
    teacher_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    assignments: Optional[List[TeacherAssignmentInput]] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data):
        if isinstance(data, dict):
            if not data.get("full_name") and data.get("name"):
                data["full_name"] = data["name"]
        return data


class SubjectTeacherAssignmentResponse(BaseModel):
    id: int
    class_id: int
    class_name: str
    department: str
    year: int
    section: str
    subject_id: int
    subject_name: str
    subject_code: str

    model_config = ConfigDict(from_attributes=True)


class SubjectTeacherDetailResponse(BaseModel):
    id: int
    teacher_id: Optional[str] = None
    username: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    assigned_subjects: List[SubjectTeacherAssignmentResponse] = []
    assignments: List[SubjectTeacherAssignmentResponse] = []

    model_config = ConfigDict(from_attributes=True)
