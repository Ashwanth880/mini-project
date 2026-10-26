from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Student(Base):
    """
    Represents an enrolled student belonging to a class.
    """
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    register_number = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False, index=True)
    year = Column(Integer, nullable=False, default=1)
    section = Column(String(10), nullable=False, default="A")
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    face_enrolled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    class_group = relationship("Class", back_populates="students")
    faces = relationship("StudentFace", back_populates="student", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")

    # Smart College Extended Relationships
    user_account = relationship("User", back_populates="student_profile", uselist=False)
    assignment_submissions = relationship("AssignmentSubmission", back_populates="student", cascade="all, delete-orphan")
    academic_records = relationship("StudentAcademicRecord", back_populates="student", cascade="all, delete-orphan")


class StudentFace(Base):
    """
    Stores enrolled facial embeddings and portrait references for a student.
    Supports storing face embeddings (e.g. 128D/512D float vectors serialized as JSON).
    """
    __tablename__ = "student_faces"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    # Stored 128D or 512D float array serialized as JSON (optional until CV embedding pipeline runs)
    embedding = Column(Text, nullable=True, default="")
    image_path = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    student = relationship("Student", back_populates="faces")
