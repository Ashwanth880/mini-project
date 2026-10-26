"""
Database initialization and seeding script.
Creates all SQLite tables and seeds sample data for development with bcrypt hashed passwords.
"""

import json
from app.database import engine, Base, SessionLocal
from app.utils.security import hash_password
import app.models  # Ensures all 8 models are loaded in Base.metadata
from app.models import (
    User,
    UserRole,
    Class,
    Subject,
    ClassSubject,
    Student,
    StudentFace,
)


def initialize_database(seed_data: bool = True):
    """Creates all tables defined in SQLAlchemy models."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully:")
    for table_name in Base.metadata.tables.keys():
        print(f" - {table_name}")

    if seed_data:
        db = SessionLocal()
        try:
            # Check if admin already exists
            existing_admin = db.query(User).filter(User.username == "admin").first()
            if not existing_admin:
                print("Seeding initial administrator and faculty with bcrypt passwords...")
                admin_user = User(
                    username="admin",
                    email="admin@college.edu",
                    hashed_password=hash_password("admin123"),
                    full_name="System Administrator",
                    role=UserRole.ADMIN,
                    department="Administration",
                )
                class_teacher = User(
                    username="sharma",
                    email="sharma@college.edu",
                    hashed_password=hash_password("teacher123"),
                    full_name="Dr. A. Sharma",
                    role=UserRole.CLASS_TEACHER,
                    department="Computer Science",
                )
                subject_teacher = User(
                    username="patel",
                    email="patel@college.edu",
                    hashed_password=hash_password("teacher123"),
                    full_name="Prof. R. Patel",
                    role=UserRole.SUBJECT_TEACHER,
                    department="Computer Science",
                )
                db.add_all([admin_user, class_teacher, subject_teacher])
                db.commit()

                # Seed sample Class
                print("Seeding sample Class...")
                sample_class = Class(
                    name="CSE - 3rd Year - Section A",
                    department="Computer Science",
                    year=3,
                    section="A",
                    class_teacher_id=class_teacher.id,
                )
                db.add(sample_class)
                db.commit()

                # Seed sample Subject
                print("Seeding sample Subject...")
                sample_subject = Subject(
                    code="CS302",
                    name="Computer Vision & Deep Learning",
                    department="Computer Science",
                )
                db.add(sample_subject)
                db.commit()

                # Link ClassSubject
                print("Linking Class and Subject with Teacher...")
                class_sub = ClassSubject(
                    class_id=sample_class.id,
                    subject_id=sample_subject.id,
                    teacher_id=subject_teacher.id,
                )
                db.add(class_sub)
                db.commit()

                # Seed sample Students
                print("Seeding sample Students...")
                students = [
                    Student(
                        roll_number="21CS001",
                        register_number="910021104001",
                        full_name="Aditya Kumar",
                        department="Computer Science",
                        year=3,
                        section="A",
                        class_id=sample_class.id,
                        face_enrolled=True,
                    ),
                    Student(
                        roll_number="21CS002",
                        register_number="910021104002",
                        full_name="Bhavya Sen",
                        department="Computer Science",
                        year=3,
                        section="A",
                        class_id=sample_class.id,
                        face_enrolled=True,
                    ),
                    Student(
                        roll_number="21CS003",
                        register_number="910021104003",
                        full_name="Chetan Verma",
                        department="Computer Science",
                        year=3,
                        section="A",
                        class_id=sample_class.id,
                        face_enrolled=False,
                    ),
                ]
                db.add_all(students)
                db.commit()

                # Add dummy face embedding for enrolled student (128-dimensional vector representation)
                dummy_vector = [0.05 * (i % 7) for i in range(128)]
                face_record = StudentFace(
                    student_id=students[0].id,
                    embedding=json.dumps(dummy_vector),
                    image_path="sample_aditya.jpg",
                )
                db.add(face_record)
                db.commit()

                print("Sample development data seeded successfully with bcrypt hashes!")
            else:
                # Update existing user passwords to bcrypt if they were placeholders
                admin_user = db.query(User).filter(User.username == "admin").first()
                if admin_user and not admin_user.hashed_password.startswith("$2b$"):
                    admin_user.hashed_password = hash_password("admin123")
                teacher1 = db.query(User).filter(User.username == "sharma").first()
                if teacher1 and not teacher1.hashed_password.startswith("$2b$"):
                    teacher1.hashed_password = hash_password("teacher123")
                teacher2 = db.query(User).filter(User.username == "patel").first()
                if teacher2 and not teacher2.hashed_password.startswith("$2b$"):
                    teacher2.hashed_password = hash_password("teacher123")
                db.commit()
                print("Updated existing user passwords to valid bcrypt hashes.")
        finally:
            db.close()


if __name__ == "__main__":
    initialize_database(seed_data=True)
