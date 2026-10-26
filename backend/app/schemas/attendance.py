from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.attendance import AttendanceStatus


class AttendanceRecordBase(BaseModel):
    student_id: int
    class_id: int
    subject_id: int
    teacher_id: Optional[int] = None
    date: date
    period: int = 1
    status: AttendanceStatus = AttendanceStatus.PRESENT
    confidence: Optional[float] = None
    attendance_image_id: Optional[int] = None
    bounding_box: Optional[str] = None
    is_manual: bool = False


class AttendanceRecordCreate(AttendanceRecordBase):
    pass


class AttendanceRecordResponse(AttendanceRecordBase):
    id: int
    student_roll: Optional[str] = None
    student_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceImageResponse(BaseModel):
    id: int
    image_path: str
    class_id: int
    subject_id: int
    total_faces_detected: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceConfirmationRequest(BaseModel):
    confirmed_records: List[AttendanceRecordBase]


class StudentAttendancePreview(BaseModel):
    student_id: int
    roll_number: str
    register_number: Optional[str] = None
    full_name: str
    status: str  # "PRESENT" | "ABSENT"
    confidence: float
    similarity: float
    is_detected: bool
    face_enrolled: bool
    bounding_box: Optional[List[int]] = None  # [x, y, w, h]


class UnknownDetection(BaseModel):
    box: List[int]
    detection_confidence: float
    similarity: float
    status: str  # "UNKNOWN" | "LOW_CONFIDENCE"


class AttendanceAnalysisResponse(BaseModel):
    attendance_image_id: Optional[int]
    image_url: Optional[str]
    image_path: Optional[str]
    annotated_image_url: Optional[str] = None
    annotated_image_path: Optional[str] = None
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str
    date: str
    period: int
    threshold_applied: float
    total_students_in_class: int
    total_faces_detected: int
    recognized_count: int
    unknown_count: int
    present_count: int
    absent_count: int
    preview_records: List[StudentAttendancePreview]
    unknown_detections: List[UnknownDetection]


class AttendanceConfirmationResponse(BaseModel):
    success: bool
    message: str
    class_id: int
    subject_id: int
    date: str
    period: int
    total_records_saved: int
    present_count: int
    absent_count: int
    records: List[AttendanceRecordResponse]

