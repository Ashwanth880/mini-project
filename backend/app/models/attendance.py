import enum
from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class AttendanceImage(Base):
    """
    Stores captured classroom group photos used for computer vision attendance processing.
    """
    __tablename__ = "attendance_images"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String(255), nullable=False)
    uploaded_by_teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    total_faces_detected = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    uploaded_by = relationship("User", back_populates="attendance_images")
    class_group = relationship("Class", back_populates="attendance_images")
    subject = relationship("Subject", back_populates="attendance_images")
    attendances = relationship("Attendance", back_populates="attendance_image", cascade="all, delete-orphan")


class Attendance(Base):
    """
    Individual student attendance record containing:
    - student
    - class
    - subject
    - teacher
    - date
    - period
    - status
    - confidence
    - attendance image reference
    """
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "class_id", "subject_id", "date", "period", name="uq_attendance_student_session"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    date = Column(Date, default=date.today, nullable=False, index=True)
    period = Column(Integer, nullable=False, default=1)
    status = Column(Enum(AttendanceStatus), default=AttendanceStatus.ABSENT, nullable=False)
    confidence = Column(Float, nullable=True)  # Face recognition confidence score (0.0 to 1.0)
    attendance_image_id = Column(Integer, ForeignKey("attendance_images.id", ondelete="SET NULL"), nullable=True, index=True)
    bounding_box = Column(Text, nullable=True)  # JSON [x, y, w, h] coordinates of detected face
    is_manual = Column(Boolean, default=False, nullable=False)  # True if manually modified by teacher
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    student = relationship("Student", back_populates="attendances")
    class_group = relationship("Class", back_populates="attendances")
    subject = relationship("Subject", back_populates="attendances")
    teacher = relationship("User", back_populates="attendance_marked")
    attendance_image = relationship("AttendanceImage", back_populates="attendances")
