"""
Tests for Smart College Management models - relationships, constraints, and schema validation.
Covers: Assignment, AssignmentSubmission, OnlineClass, Timetable, ExamTimetable,
        CollegeEvent, Announcement, StudyMaterial, Notification, StudentAcademicRecord.
"""
import pytest
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database import Base
import app.models  # registers all models on Base.metadata


# ---------------------------------------------------------------------------
# In-memory SQLite test database fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def seed_base_data(db):
    """Create one User, one Class, one Subject, one Student and return them."""
    from app.models import User, UserRole, Class, Subject, Student

    user = User(username="teacher1", email="t1@test.com",
                hashed_password="x", full_name="Teacher One",
                role=UserRole.SUBJECT_TEACHER, department="CS")
    db.add(user)
    db.flush()

    cls = Class(name="CS-3A", department="CS", year=3, section="A")
    db.add(cls)
    db.flush()

    subject = Subject(code="CS301", name="Data Structures", department="CS")
    db.add(subject)
    db.flush()

    student = Student(roll_number="21CS001", register_number="R2021001",
                      full_name="Alice", department="CS", year=3, section="A",
                      class_id=cls.id)
    db.add(student)
    db.flush()

    return user, cls, subject, student


# ---------------------------------------------------------------------------
# 1. Assignment Tests
# ---------------------------------------------------------------------------

class TestAssignment:
    def test_create_assignment(self, db):
        user, cls, subject, student = seed_base_data(db)
        from app.models.college_management import Assignment, AssignmentStatus
        a = Assignment(
            title="DS Lab 1",
            subject_id=subject.id,
            class_id=cls.id,
            teacher_id=user.id,
            deadline=_now() + timedelta(days=7),
            maximum_marks=50.0,
            status=AssignmentStatus.PUBLISHED,
        )
        db.add(a)
        db.commit()
        assert a.id is not None
        assert a.maximum_marks == 50.0

    def test_assignment_relationship_to_subject(self, db):
        from app.models.college_management import Assignment
        a = db.query(Assignment).first()
        assert a.subject is not None
        assert a.class_group is not None
        assert a.teacher is not None


# ---------------------------------------------------------------------------
# 2. AssignmentSubmission Tests
# ---------------------------------------------------------------------------

class TestAssignmentSubmission:
    def test_submit_assignment(self, db):
        from app.models.college_management import Assignment, AssignmentSubmission, SubmissionStatus
        assignment = db.query(Assignment).first()
        student = db.query(app.models.Student).first()
        sub = AssignmentSubmission(
            assignment_id=assignment.id,
            student_id=student.id,
            submission_text="My answer",
            submission_status=SubmissionStatus.SUBMITTED,
        )
        db.add(sub)
        db.commit()
        assert sub.id is not None

    def test_duplicate_submission_raises(self, db):
        from app.models.college_management import Assignment, AssignmentSubmission, SubmissionStatus
        assignment = db.query(Assignment).first()
        student = db.query(app.models.Student).first()
        dup = AssignmentSubmission(
            assignment_id=assignment.id,
            student_id=student.id,
            submission_text="Duplicate",
            submission_status=SubmissionStatus.SUBMITTED,
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 3. OnlineClass Tests
# ---------------------------------------------------------------------------

class TestOnlineClass:
    def test_create_online_class(self, db):
        from app.models.college_management import OnlineClass, OnlineClassStatus
        user = db.query(app.models.User).first()
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        oc = OnlineClass(
            title="DS Lecture 1",
            subject_id=subject.id,
            class_id=cls.id,
            teacher_id=user.id,
            meeting_provider="Google Meet",
            meeting_url="https://meet.google.com/abc-xyz",
            start_time=_now() + timedelta(hours=1),
            end_time=_now() + timedelta(hours=2),
            status=OnlineClassStatus.SCHEDULED,
        )
        db.add(oc)
        db.commit()
        assert oc.id is not None

    def test_online_class_relationships(self, db):
        from app.models.college_management import OnlineClass
        oc = db.query(OnlineClass).first()
        assert oc.subject is not None
        assert oc.class_group is not None


# ---------------------------------------------------------------------------
# 4. Timetable Tests
# ---------------------------------------------------------------------------

class TestTimetable:
    def test_create_timetable_slot(self, db):
        from app.models.college_management import Timetable
        user = db.query(app.models.User).first()
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        slot = Timetable(
            class_id=cls.id, subject_id=subject.id, teacher_id=user.id,
            weekday="Monday", period=1, start_time="09:00", end_time="09:50",
            classroom="Hall 101",
        )
        db.add(slot)
        db.commit()
        assert slot.id is not None

    def test_duplicate_slot_raises(self, db):
        from app.models.college_management import Timetable
        user = db.query(app.models.User).first()
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        dup = Timetable(
            class_id=cls.id, subject_id=subject.id, teacher_id=user.id,
            weekday="Monday", period=1, start_time="09:00", end_time="09:50",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 5. ExamTimetable Tests
# ---------------------------------------------------------------------------

class TestExamTimetable:
    def test_create_exam_timetable(self, db):
        from app.models.college_management import ExamTimetable
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        et = ExamTimetable(
            exam_name="Mid-Term 2026",
            subject_id=subject.id,
            class_id=cls.id,
            date=date(2026, 11, 15),
            start_time="10:00",
            end_time="13:00",
            venue="Main Hall",
        )
        db.add(et)
        db.commit()
        assert et.id is not None

    def test_duplicate_exam_slot_raises(self, db):
        from app.models.college_management import ExamTimetable
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        dup = ExamTimetable(
            exam_name="Mid-Term 2026",
            subject_id=subject.id,
            class_id=cls.id,
            date=date(2026, 11, 15),
            start_time="10:00",
            end_time="13:00",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 6. CollegeEvent Tests
# ---------------------------------------------------------------------------

class TestCollegeEvent:
    def test_create_college_event(self, db):
        from app.models.college_management import CollegeEvent
        user = db.query(app.models.User).first()
        ev = CollegeEvent(
            event_title="Tech Fest 2026",
            description="Annual tech symposium",
            date=_now() + timedelta(days=30),
            category="Technical",
            audience="ALL",
            created_by_user_id=user.id,
        )
        db.add(ev)
        db.commit()
        assert ev.id is not None

    def test_event_created_by_relationship(self, db):
        from app.models.college_management import CollegeEvent
        ev = db.query(CollegeEvent).first()
        assert ev.created_by is not None


# ---------------------------------------------------------------------------
# 7. Announcement Tests
# ---------------------------------------------------------------------------

class TestAnnouncement:
    def test_create_announcement(self, db):
        from app.models.college_management import Announcement, AnnouncementPriority
        user = db.query(app.models.User).first()
        ann = Announcement(
            title="Campus Closed",
            message="Campus will be closed on Nov 14.",
            author_id=user.id,
            target_audience="ALL",
            priority=AnnouncementPriority.HIGH,
        )
        db.add(ann)
        db.commit()
        assert ann.id is not None

    def test_announcement_author_relationship(self, db):
        from app.models.college_management import Announcement
        ann = db.query(Announcement).first()
        assert ann.author is not None


# ---------------------------------------------------------------------------
# 8. StudyMaterial Tests
# ---------------------------------------------------------------------------

class TestStudyMaterial:
    def test_create_study_material(self, db):
        from app.models.college_management import StudyMaterial
        user = db.query(app.models.User).first()
        cls = db.query(app.models.Class).first()
        subject = db.query(app.models.Subject).first()
        mat = StudyMaterial(
            title="DS Notes Unit 1",
            subject_id=subject.id,
            class_id=cls.id,
            teacher_id=user.id,
            file_url="/uploads/ds_unit1.pdf",
            file_size_bytes=102400,
        )
        db.add(mat)
        db.commit()
        assert mat.id is not None

    def test_study_material_teacher_relationship(self, db):
        from app.models.college_management import StudyMaterial
        mat = db.query(StudyMaterial).first()
        assert mat.teacher is not None


# ---------------------------------------------------------------------------
# 9. Notification Tests
# ---------------------------------------------------------------------------

class TestNotification:
    def test_create_notification(self, db):
        from app.models.college_management import Notification, NotificationType
        user = db.query(app.models.User).first()
        notif = Notification(
            recipient_id=user.id,
            title="Assignment Due",
            message="DS Lab 1 is due in 24 hours.",
            type=NotificationType.ASSIGNMENT,
            read_status=False,
        )
        db.add(notif)
        db.commit()
        assert notif.id is not None

    def test_notification_recipient_relationship(self, db):
        from app.models.college_management import Notification
        notif = db.query(Notification).first()
        assert notif.recipient is not None
        assert notif.read_status is False

    def test_mark_notification_read(self, db):
        from app.models.college_management import Notification
        notif = db.query(Notification).first()
        notif.read_status = True
        db.commit()
        db.refresh(notif)
        assert notif.read_status is True


# ---------------------------------------------------------------------------
# 10. StudentAcademicRecord Tests
# ---------------------------------------------------------------------------

class TestStudentAcademicRecord:
    def test_create_academic_record(self, db):
        from app.models.college_management import StudentAcademicRecord
        student = db.query(app.models.Student).first()
        subject = db.query(app.models.Subject).first()
        rec = StudentAcademicRecord(
            student_id=student.id,
            subject_id=subject.id,
            semester=5,
            academic_year="2025-2026",
            assessment_type="Internal Assessment 1",
            internal_marks=38.5,
            max_marks=50.0,
        )
        db.add(rec)
        db.commit()
        assert rec.id is not None

    def test_duplicate_record_raises(self, db):
        from app.models.college_management import StudentAcademicRecord
        student = db.query(app.models.Student).first()
        subject = db.query(app.models.Subject).first()
        dup = StudentAcademicRecord(
            student_id=student.id,
            subject_id=subject.id,
            semester=5,
            academic_year="2025-2026",
            assessment_type="Internal Assessment 1",
            internal_marks=40.0,
            max_marks=50.0,
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_academic_record_student_relationship(self, db):
        from app.models.college_management import StudentAcademicRecord
        rec = db.query(StudentAcademicRecord).first()
        assert rec.student is not None
        assert rec.subject is not None


# ---------------------------------------------------------------------------
# Schema Validation Tests (no DB needed)
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_assignment_create_valid(self):
        from app.schemas.college_management import AssignmentCreate
        a = AssignmentCreate(
            title="Test Assignment",
            subject_id=1, class_id=1,
            deadline=_now() + timedelta(days=5),
            maximum_marks=100.0,
        )
        assert a.title == "Test Assignment"

    def test_online_class_end_before_start_fails(self):
        from app.schemas.college_management import OnlineClassCreate
        from pydantic import ValidationError
        now = _now()
        with pytest.raises(ValidationError):
            OnlineClassCreate(
                title="Test", subject_id=1, class_id=1,
                meeting_url="https://meet.example.com",
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=1),  # end before start
            )

    def test_timetable_invalid_weekday_fails(self):
        from app.schemas.college_management import TimetableCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TimetableCreate(
                class_id=1, subject_id=1,
                weekday="Sunday",  # not a valid teaching day
                period=1, start_time="09:00", end_time="09:50",
            )

    def test_academic_record_marks_exceed_max_fails(self):
        from app.schemas.college_management import StudentAcademicRecordCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            StudentAcademicRecordCreate(
                student_id=1, subject_id=1,
                semester=3, academic_year="2025-2026",
                assessment_type="IA1",
                internal_marks=110.0,  # exceeds max_marks=100
                max_marks=100.0,
            )

    def test_academic_year_format_validated(self):
        from app.schemas.college_management import StudentAcademicRecordCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            StudentAcademicRecordCreate(
                student_id=1, subject_id=1,
                semester=3, academic_year="2025",  # missing YYYY-YYYY format
                assessment_type="IA1",
                internal_marks=40.0, max_marks=50.0,
            )

    def test_notification_mark_read_requires_list(self):
        from app.schemas.college_management import NotificationMarkRead
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NotificationMarkRead(notification_ids=[])  # min_length=1

    def test_study_material_create(self):
        from app.schemas.college_management import StudyMaterialCreate
        mat = StudyMaterialCreate(
            title="Unit 2 Notes",
            subject_id=1, class_id=1,
            file_url="/uploads/unit2.pdf",
        )
        assert mat.file_url == "/uploads/unit2.pdf"
