import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    CLASS_TEACHER = "CLASS_TEACHER"
    SUBJECT_TEACHER = "SUBJECT_TEACHER"
    STUDENT = "STUDENT"


class User(Base):
    """
    Represents faculty, administrators, teachers, and student accounts in the institution.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(String(50), unique=True, index=True, nullable=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.SUBJECT_TEACHER, nullable=False)
    department = Column(String(100), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Core Relationships
    classes_mentored = relationship("Class", back_populates="class_teacher")
    class_subjects = relationship("ClassSubject", back_populates="teacher")
    attendance_marked = relationship("Attendance", back_populates="teacher")
    attendance_images = relationship("AttendanceImage", back_populates="uploaded_by")

    # Smart College Extended Relationships
    student_profile = relationship("Student", back_populates="user_account", foreign_keys=[student_id])
    assignments_created = relationship("Assignment", back_populates="teacher")
    online_classes = relationship("OnlineClass", back_populates="teacher")
    timetable_slots = relationship("Timetable", back_populates="teacher")
    study_materials_uploaded = relationship("StudyMaterial", back_populates="teacher")
    announcements_posted = relationship("Announcement", back_populates="author")
    college_events_created = relationship("CollegeEvent", back_populates="created_by")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")
