"""
Pydantic validation schemas for the 10 Smart College Management models:
Assignment, AssignmentSubmission, OnlineClass, Timetable, ExamTimetable,
CollegeEvent, Announcement, StudyMaterial, Notification, StudentAcademicRecord.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.college_management import (
    AssignmentStatus,
    SubmissionStatus,
    OnlineClassStatus,
    NotificationType,
    AnnouncementPriority,
)


# ===========================================================================
# 1. Assignment Schemas
# ===========================================================================

class AssignmentBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    subject_id: int
    class_id: int
    teacher_id: Optional[int] = None
    deadline: datetime
    maximum_marks: float = Field(default=100.0, gt=0)
    attachments: Optional[str] = None
    status: AssignmentStatus = AssignmentStatus.PUBLISHED


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    maximum_marks: Optional[float] = Field(None, gt=0)
    attachments: Optional[str] = None
    status: Optional[AssignmentStatus] = None


class AssignmentResponse(AssignmentBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 2. AssignmentSubmission Schemas
# ===========================================================================

class AssignmentSubmissionBase(BaseModel):
    assignment_id: int
    student_id: int
    submission_text: Optional[str] = None
    uploaded_file: Optional[str] = Field(None, max_length=500)


class AssignmentSubmissionCreate(AssignmentSubmissionBase):
    pass


class AssignmentSubmissionUpdate(BaseModel):
    marks: Optional[float] = Field(None, ge=0)
    feedback: Optional[str] = None
    submission_status: Optional[SubmissionStatus] = None


class AssignmentSubmissionResponse(AssignmentSubmissionBase):
    id: int
    submitted_date: datetime
    marks: Optional[float] = None
    feedback: Optional[str] = None
    submission_status: SubmissionStatus

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 3. OnlineClass Schemas
# ===========================================================================

class OnlineClassBase(BaseModel):
    title: str = Field(..., max_length=200)
    subject_id: int
    class_id: int
    teacher_id: Optional[int] = None
    meeting_provider: str = Field(default="Google Meet", max_length=50)
    meeting_url: str = Field(..., max_length=500)
    start_time: datetime
    end_time: datetime
    status: OnlineClassStatus = OnlineClassStatus.SCHEDULED

    @field_validator("end_time")
    @classmethod
    def end_must_be_after_start(cls, end: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and end <= start:
            raise ValueError("end_time must be after start_time")
        return end


class OnlineClassCreate(OnlineClassBase):
    pass


class OnlineClassUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    meeting_url: Optional[str] = Field(None, max_length=500)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[OnlineClassStatus] = None


class OnlineClassResponse(OnlineClassBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 4. Timetable Schemas
# ===========================================================================

VALID_WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}


class TimetableBase(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: Optional[int] = None
    weekday: str = Field(..., max_length=20)
    period: int = Field(..., ge=1, le=12)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    classroom: Optional[str] = Field(None, max_length=50)

    @field_validator("weekday")
    @classmethod
    def validate_weekday(cls, v: str) -> str:
        if v not in VALID_WEEKDAYS:
            raise ValueError(f"weekday must be one of {sorted(VALID_WEEKDAYS)}")
        return v


class TimetableCreate(TimetableBase):
    pass


class TimetableUpdate(BaseModel):
    teacher_id: Optional[int] = None
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    classroom: Optional[str] = Field(None, max_length=50)


class TimetableResponse(TimetableBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 5. ExamTimetable Schemas
# ===========================================================================

class ExamTimetableBase(BaseModel):
    exam_name: str = Field(..., max_length=150)
    subject_id: int
    class_id: int
    date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    venue: Optional[str] = Field(None, max_length=100)


class ExamTimetableCreate(ExamTimetableBase):
    pass


class ExamTimetableUpdate(BaseModel):
    date: Optional[date] = None
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    venue: Optional[str] = Field(None, max_length=100)


class ExamTimetableResponse(ExamTimetableBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 6. CollegeEvent Schemas
# ===========================================================================

class CollegeEventBase(BaseModel):
    event_title: str = Field(..., max_length=200)
    description: Optional[str] = None
    date: datetime
    category: str = Field(default="Academic", max_length=100)
    audience: str = Field(default="ALL", max_length=100)
    venue: Optional[str] = Field(None, max_length=150)
    created_by_user_id: Optional[int] = None


class CollegeEventCreate(CollegeEventBase):
    pass


class CollegeEventUpdate(BaseModel):
    event_title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    audience: Optional[str] = Field(None, max_length=100)
    venue: Optional[str] = Field(None, max_length=150)


class CollegeEventResponse(CollegeEventBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 7. Announcement Schemas
# ===========================================================================

class AnnouncementBase(BaseModel):
    title: str = Field(..., max_length=250)
    message: str
    author_id: Optional[int] = None
    target_class_id: Optional[int] = None
    target_audience: str = Field(default="ALL", max_length=50)
    priority: AnnouncementPriority = AnnouncementPriority.NORMAL
    expiry_date: Optional[datetime] = None


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=250)
    message: Optional[str] = None
    priority: Optional[AnnouncementPriority] = None
    target_audience: Optional[str] = Field(None, max_length=50)
    expiry_date: Optional[datetime] = None


class AnnouncementResponse(AnnouncementBase):
    id: int
    publication_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 8. StudyMaterial Schemas
# ===========================================================================

class StudyMaterialBase(BaseModel):
    title: str = Field(..., max_length=200)
    subject_id: int
    class_id: int
    teacher_id: Optional[int] = None
    description: Optional[str] = None
    file_url: str = Field(..., max_length=500)
    file_size_bytes: Optional[int] = Field(None, ge=0)


class StudyMaterialCreate(StudyMaterialBase):
    pass


class StudyMaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    file_url: Optional[str] = Field(None, max_length=500)
    file_size_bytes: Optional[int] = Field(None, ge=0)


class StudyMaterialResponse(StudyMaterialBase):
    id: int
    uploaded_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 9. Notification Schemas
# ===========================================================================

class NotificationBase(BaseModel):
    recipient_id: int
    title: str = Field(..., max_length=200)
    message: str
    type: NotificationType = NotificationType.GENERAL
    related_record: Optional[str] = Field(None, max_length=100)


class NotificationCreate(NotificationBase):
    pass


class NotificationMarkRead(BaseModel):
    notification_ids: List[int] = Field(..., min_length=1)


class NotificationResponse(NotificationBase):
    id: int
    read_status: bool
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 10. StudentAcademicRecord Schemas
# ===========================================================================

class StudentAcademicRecordBase(BaseModel):
    student_id: int
    subject_id: int
    semester: int = Field(..., ge=1, le=10)
    academic_year: str = Field(
        ..., max_length=20, pattern=r"^\d{4}-\d{4}$",
        description="Format: YYYY-YYYY e.g. 2025-2026"
    )
    assessment_type: str = Field(..., max_length=50)
    internal_marks: float = Field(..., ge=0)
    max_marks: float = Field(default=100.0, gt=0)
    remarks: Optional[str] = Field(None, max_length=255)

    @field_validator("internal_marks")
    @classmethod
    def marks_within_max(cls, v: float, info) -> float:
        max_m = info.data.get("max_marks", 100.0)
        if max_m and v > max_m:
            raise ValueError(f"internal_marks ({v}) cannot exceed max_marks ({max_m})")
        return v


class StudentAcademicRecordCreate(StudentAcademicRecordBase):
    pass


class StudentAcademicRecordUpdate(BaseModel):
    internal_marks: Optional[float] = Field(None, ge=0)
    max_marks: Optional[float] = Field(None, gt=0)
    remarks: Optional[str] = Field(None, max_length=255)


class StudentAcademicRecordResponse(StudentAcademicRecordBase):
    id: int
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)
