import enum
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ============================================================================
# Enums for Smart College Entities
# ============================================================================

class AssignmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class SubmissionStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"
    LATE = "LATE"
    RESUBMITTED = "RESUBMITTED"


class OnlineClassStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationType(str, enum.Enum):
    GENERAL = "GENERAL"
    ATTENDANCE = "ATTENDANCE"
    ASSIGNMENT = "ASSIGNMENT"
    ONLINE_CLASS = "ONLINE_CLASS"
    EXAM = "EXAM"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    GRADE = "GRADE"


class AnnouncementPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


# ============================================================================
# 1. Assignment Model
# ============================================================================

class Assignment(Base):
    """
    Represents an assignment given to a class for a specific subject by a teacher.
    Files/attachments are referenced by file URLs or relative paths (no large binary blobs).
    """
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deadline = Column(DateTime, nullable=False, index=True)
    maximum_marks = Column(Float, default=100.0, nullable=False)
    attachments = Column(Text, nullable=True)  # File path, URL, or JSON list of paths
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.PUBLISHED, nullable=False, index=True)

    # Relationships
    subject = relationship("Subject", back_populates="assignments")
    class_group = relationship("Class", back_populates="assignments")
    teacher = relationship("User", back_populates="assignments_created")
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


# ============================================================================
# 2. AssignmentSubmission Model
# ============================================================================

class AssignmentSubmission(Base):
    """
    Represents a student's submission for an assignment.
    Prevents duplicate submissions via a UniqueConstraint on (assignment_id, student_id).
    Uploaded files are stored as path/URL references.
    """
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
    )

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    submission_text = Column(Text, nullable=True)
    uploaded_file = Column(String(500), nullable=True)  # File URL or storage path
    submitted_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    marks = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    submission_status = Column(Enum(SubmissionStatus), default=SubmissionStatus.SUBMITTED, nullable=False, index=True)

    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="assignment_submissions")


# ============================================================================
# 3. OnlineClass Model
# ============================================================================

class OnlineClass(Base):
    """
    Represents a scheduled or live virtual classroom meeting.
    """
    __tablename__ = "online_classes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_provider = Column(String(50), default="Google Meet", nullable=False)  # Google Meet, Zoom, Teams, Webex
    meeting_url = Column(String(500), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(OnlineClassStatus), default=OnlineClassStatus.SCHEDULED, nullable=False, index=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    subject = relationship("Subject", back_populates="online_classes")
    class_group = relationship("Class", back_populates="online_classes")
    teacher = relationship("User", back_populates="online_classes")


# ============================================================================
# 4. Timetable Model
# ============================================================================

class Timetable(Base):
    """
    Represents weekly recurring schedule slots for a class.
    Unique constraint prevents slot conflict: (class_id, weekday, period).
    """
    __tablename__ = "timetables"
    __table_args__ = (
        UniqueConstraint("class_id", "weekday", "period", name="uq_class_weekday_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    weekday = Column(String(20), nullable=False, index=True)  # Monday, Tuesday, Wednesday, Thursday, Friday, Saturday
    period = Column(Integer, nullable=False, index=True)
    start_time = Column(String(10), nullable=False)  # e.g., "09:00"
    end_time = Column(String(10), nullable=False)    # e.g., "09:50"
    classroom = Column(String(50), nullable=True)    # e.g., "Hall 204", "Lab 2"
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    class_group = relationship("Class", back_populates="timetables")
    subject = relationship("Subject", back_populates="timetables")
    teacher = relationship("User", back_populates="timetable_slots")


# ============================================================================
# 5. ExamTimetable Model
# ============================================================================

class ExamTimetable(Base):
    """
    Represents scheduled examinations for a class and subject.
    """
    __tablename__ = "exam_timetables"
    __table_args__ = (
        UniqueConstraint("exam_name", "class_id", "subject_id", "date", name="uq_exam_class_subject_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exam_name = Column(String(150), nullable=False, index=True)  # e.g., "Mid-Term Examination 2026"
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(String(10), nullable=False)  # e.g., "10:00"
    end_time = Column(String(10), nullable=False)    # e.g., "13:00"
    venue = Column(String(100), nullable=True)       # e.g., "Main Exam Hall"
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    subject = relationship("Subject", back_populates="exam_timetables")
    class_group = relationship("Class", back_populates="exam_timetables")


# ============================================================================
# 6. CollegeEvent Model
# ============================================================================

class CollegeEvent(Base):
    """
    Represents institutional events, technical symposiums, sports, and seminars.
    """
    __tablename__ = "college_events"

    id = Column(Integer, primary_key=True, index=True)
    event_title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    date = Column(DateTime, nullable=False, index=True)
    category = Column(String(100), default="Academic", nullable=False, index=True)  # Cultural, Sports, Technical, Workshop
    audience = Column(String(100), default="ALL", nullable=False, index=True)       # ALL, STUDENTS, FACULTY, DEPARTMENT
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    venue = Column(String(150), nullable=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    created_by = relationship("User", back_populates="college_events_created")


# ============================================================================
# 7. Announcement Model
# ============================================================================

class Announcement(Base):
    """
    Represents notices and circulars broadcast by teachers or administration.
    """
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(250), nullable=False, index=True)
    message = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True)
    target_audience = Column(String(50), default="ALL", nullable=False, index=True)  # ALL, STUDENTS, TEACHERS
    priority = Column(Enum(AnnouncementPriority), default=AnnouncementPriority.NORMAL, nullable=False, index=True)
    publication_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    expiry_date = Column(DateTime, nullable=True)

    # Relationships
    author = relationship("User", back_populates="announcements_posted")
    target_class = relationship("Class", back_populates="announcements")


# ============================================================================
# 8. StudyMaterial Model
# ============================================================================

class StudyMaterial(Base):
    """
    Represents course notes, lecture slides, and syllabus files uploaded by teachers.
    File references are stored as URLs / file system paths (no large binary blobs).
    """
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    file_url = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    uploaded_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    subject = relationship("Subject", back_populates="study_materials")
    class_group = relationship("Class", back_populates="study_materials")
    teacher = relationship("User", back_populates="study_materials_uploaded")


# ============================================================================
# 9. Notification Model
# ============================================================================

class Notification(Base):
    """
    Represents in-app notifications targeted to individual users (students, teachers, admins).
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(Enum(NotificationType), default=NotificationType.GENERAL, nullable=False, index=True)
    related_record = Column(String(100), nullable=True)  # e.g., "assignment:5", "attendance:12"
    read_status = Column(Boolean, default=False, nullable=False, index=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    recipient = relationship("User", back_populates="notifications")


# ============================================================================
# 10. StudentAcademicRecord Model
# ============================================================================

class StudentAcademicRecord(Base):
    """
    Represents student marks, internal assessments, semester exams, and performance metrics.
    Prevents duplicate entry for the same assessment type in a subject and semester.
    """
    __tablename__ = "student_academic_records"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject_id",
            "semester",
            "academic_year",
            "assessment_type",
            name="uq_student_assessment_record",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    semester = Column(Integer, nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, index=True)  # e.g., "2025-2026"
    assessment_type = Column(String(50), nullable=False, index=True)  # e.g., "Internal Assessment 1", "Semester End Exam"
    internal_marks = Column(Float, nullable=False)
    max_marks = Column(Float, default=100.0, nullable=False)
    remarks = Column(String(255), nullable=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    student = relationship("Student", back_populates="academic_records")
    subject = relationship("Subject", back_populates="academic_records")
