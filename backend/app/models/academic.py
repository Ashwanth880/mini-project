from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Class(Base):
    """
    Represents an academic class / batch / section
    (e.g., Department: Computer Science, Year: 3, Section: A).
    """
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    department = Column(String(100), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    class_teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Core Relationships
    class_teacher = relationship("User", back_populates="classes_mentored")
    students = relationship("Student", back_populates="class_group", cascade="all, delete-orphan")
    class_subjects = relationship("ClassSubject", back_populates="class_group", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="class_group", cascade="all, delete-orphan")
    attendance_images = relationship("AttendanceImage", back_populates="class_group", cascade="all, delete-orphan")

    # Smart College Extended Relationships
    assignments = relationship("Assignment", back_populates="class_group", cascade="all, delete-orphan")
    online_classes = relationship("OnlineClass", back_populates="class_group", cascade="all, delete-orphan")
    timetables = relationship("Timetable", back_populates="class_group", cascade="all, delete-orphan")
    exam_timetables = relationship("ExamTimetable", back_populates="class_group", cascade="all, delete-orphan")
    study_materials = relationship("StudyMaterial", back_populates="class_group", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="target_class", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("department", "year", "section", name="uq_dept_year_section"),
    )


class Subject(Base):
    """
    Represents a course/subject offered in the curriculum
    (e.g., Code: CS302, Name: Computer Vision).
    """
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    department = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Core Relationships
    class_subjects = relationship("ClassSubject", back_populates="subject", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="subject")
    attendance_images = relationship("AttendanceImage", back_populates="subject")

    # Smart College Extended Relationships
    assignments = relationship("Assignment", back_populates="subject", cascade="all, delete-orphan")
    online_classes = relationship("OnlineClass", back_populates="subject", cascade="all, delete-orphan")
    timetables = relationship("Timetable", back_populates="subject", cascade="all, delete-orphan")
    exam_timetables = relationship("ExamTimetable", back_populates="subject", cascade="all, delete-orphan")
    study_materials = relationship("StudyMaterial", back_populates="subject", cascade="all, delete-orphan")
    academic_records = relationship("StudentAcademicRecord", back_populates="subject", cascade="all, delete-orphan")


class ClassSubject(Base):
    """
    Association linking which subject is taught to which class by which teacher.
    """
    __tablename__ = "class_subjects"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    class_group = relationship("Class", back_populates="class_subjects")
    subject = relationship("Subject", back_populates="class_subjects")
    teacher = relationship("User", back_populates="class_subjects")

    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "teacher_id", name="uq_class_subject_teacher"),
    )
