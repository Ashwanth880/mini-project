# Smart College Management System — Architectural Analysis & Extension Plan

## 1. Executive Summary

This document presents a comprehensive analysis of the existing **One-Click Attendance System** and outlines the architectural plan to extend it into a full-fledged **Smart College Management System** featuring dedicated **Teacher** and **Student** portals.

All existing core features—notably the OpenCV AI facial recognition pipeline, attendance verification canvas, admin operations, and reporting—will be **100% preserved and protected**.

---

## 2. Existing Architecture & Project Inventory

### 2.1 Technology Stack
* **Backend Framework**: Python 3.10+ with **FastAPI** (`0.110.0+`), Pydantic v2 Settings & Schemas.
* **Database & ORM**: **SQLite** (`backend/attendance.db`) via **SQLAlchemy 2.0**.
* **Authentication & Security**: JWT Bearer tokens (`PyJWT`), password hashing via `bcrypt`.
* **Computer Vision Pipeline**:
  * Face Detection: OpenCV DNN YuNet (`face_detection_yunet_2023mar.onnx`) & Haar Cascade fallback.
  * Face Recognition / Feature Extraction: OpenCV SFace (`face_recognition_sface_2021dec.onnx`, 128-dimensional embedding vectors).
  * Matching: Cosine similarity / Euclidean distance against enrolled vector database with classroom-scoped filtering.
* **Frontend**: HTML5, Vanilla CSS3 (`styles.css`), JavaScript ES6+ (`api.js`, `app.js`), Bootstrap 5.3.3, Bootstrap Icons.
* **Testing Suites**: 14 test modules in `backend/tests/` and 3 root verification scripts covering live HTTP sockets, CV pipelines, role-based authorization, and reporting.

---

### 2.2 Project Directory Tree

```
MINI PROJET_11/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entry, CORS, router mounts & static mounts
│   │   ├── config.py                   # Pydantic Settings (.env configuration & folder creation)
│   │   ├── database.py                 # SQLAlchemy engine, SessionLocal, init_db()
│   │   ├── models/                     # SQLAlchemy ORM Database Models
│   │   │   ├── user.py                 # User & UserRole (ADMIN, CLASS_TEACHER, SUBJECT_TEACHER)
│   │   │   ├── student.py              # Student, StudentFace (embeddings)
│   │   │   ├── academic.py             # Class, Subject, ClassSubject
│   │   │   └── attendance.py           # Attendance, AttendanceImage, AttendanceStatus
│   │   ├── schemas/                    # Pydantic Request & Response Models
│   │   │   ├── user.py, student.py, academic.py, attendance.py
│   │   ├── api/                        # Route Handlers (/api/v1)
│   │   │   ├── deps.py                 # Role authorization dependencies & token decoding
│   │   │   ├── auth.py                 # /auth/register, /auth/login, /auth/me
│   │   │   ├── admin.py                # CRUD for classes, subjects, teachers, assignments, students, logs
│   │   │   ├── teachers.py             # Class teacher & subject teacher specific endpoints
│   │   │   ├── students.py             # Student registration & portrait face enrollment
│   │   │   ├── classes.py, subjects.py # Academic entity CRUD
│   │   │   ├── assignments.py          # Class-Subject-Teacher mapping endpoints
│   │   │   └── attendance.py           # CV Photo analysis, confirmation, report aggregations
│   │   ├── services/                   # Business and Machine Learning Logic
│   │   │   ├── face_service.py         # Student portrait validation, YuNet detection, SFace embeddings
│   │   │   ├── face_recognition.py     # Classroom wide-shot multi-face matching & bounding boxes
│   │   │   ├── attendance_service.py   # Match processing pipeline
│   │   │   └── reports_service.py      # Attendance analytics & CSV generation
│   │   └── utils/security.py           # Password hashing & JWT helpers
│   ├── attendance.db                   # Live SQLite database file
│   └── tests/                          # Automated backend test suites
├── frontend/
│   ├── index.html                      # Unified Single Page Application (SPA) dashboard
│   ├── css/styles.css                  # Custom styles, responsive dark-sidebar, cards, pills
│   └── js/
│       ├── api.js                      # Fetch API wrapper with JWT Bearer handling
│       └── app.js                      # UI routing, state management, role-based navigation
├── data/
│   ├── faces/                          # Enrolled student face portraits
│   ├── attendance_photos/              # Uploaded classroom session group photos
│   └── models/                         # Pre-trained ONNX CV weights (YuNet, SFace)
└── README.md                           # Documentation
```

---

## 3. Existing Models and Relationships

```mermaid
erDiagram
    User ||--o{ Class : "mentors (as class_teacher)"
    User ||--o{ ClassSubject : "teaches"
    User ||--o{ Attendance : "records"
    User ||--o{ AttendanceImage : "uploads"

    Class ||--o{ Student : "enrolled in"
    Class ||--o{ ClassSubject : "has"
    Class ||--o{ Attendance : "session for"
    Class ||--o{ AttendanceImage : "belongs to"

    Subject ||--o{ ClassSubject : "assigned in"
    Subject ||--o{ Attendance : "subject of"
    Subject ||--o{ AttendanceImage : "session subject"

    Student ||--o{ StudentFace : "has face vectors"
    Student ||--o{ Attendance : "records for"

    AttendanceImage ||--o{ Attendance : "source photo"
```

### Entity Details:
1. **`User` (`users`)**:
   - Represents staff: Admin, Class Teachers, Subject Teachers.
   - Roles: `ADMIN`, `CLASS_TEACHER`, `SUBJECT_TEACHER`.
   - Fields: `username`, `email`, `hashed_password`, `full_name`, `role`, `department`.
2. **`Class` (`classes`)**:
   - Sections (e.g., Computer Science, Year 3, Section A).
   - Foreign key: `class_teacher_id -> users.id`.
   - Unique constraint: `(department, year, section)`.
3. **`Subject` (`subjects`)**:
   - Course curriculum (e.g., Code: `CS302`, Name: `Computer Vision`).
4. **`ClassSubject` (`class_subjects`)**:
   - Junction table linking `(class_id, subject_id, teacher_id)`.
5. **`Student` (`students`)**:
   - Student demographic record: `roll_number`, `register_number`, `full_name`, `department`, `year`, `section`, `class_id`, `email`, `phone`, `is_active`, `face_enrolled`.
6. **`StudentFace` (`student_faces`)**:
   - Enrolled biometric vectors: `student_id`, `embedding` (JSON serialized float array), `image_path`, `is_primary`.
7. **`AttendanceImage` (`attendance_images`)**:
   - Session group photo: `image_path`, `class_id`, `subject_id`, `uploaded_by_teacher_id`, `total_faces_detected`.
8. **`Attendance` (`attendance`)**:
   - Single student session log: `student_id`, `class_id`, `subject_id`, `teacher_id`, `date`, `period`, `status` (`PRESENT`, `ABSENT`, `LATE`, `EXCUSED`), `confidence`, `bounding_box`, `is_manual`.

---

## 4. Current Gaps vs. Smart College Management System

| Feature Area | Current State (Attendance Only) | Target State (Smart College System) |
|---|---|---|
| **Student Access** | No login capability. Students are passive records in the database. | **Dedicated Student Portal** with authentication (register number / student email + password), viewing attendance, timetables, assignments, and grades. |
| **Teacher Workflow** | Focuses solely on attendance capture and student rosters. | **Extended Teacher Portal**: Timetable schedule, assignment publishing & grading, internal marks management, and announcements. |
| **Academic Timetable** | Not modeled in DB. | Weekly interactive timetable for classes, subjects, teachers, and student schedules. |
| **Coursework & Homework**| Absent. | Assignment repository with due dates, file attachments, student submission portal, and teacher grading. |
| **Grades & Marks** | Absent. | Internal assessment marks entry, semester test tracking, and student performance transcripts. |
| **Communication** | No notice system. | Noticeboard/Announcements system targeted to students, teachers, or specific classes. |

---

## 5. Proposed Architecture Extensions

### 5.1 New Database Models

1. **Student User Authentication (`UserRole.STUDENT`)**:
   - Extend `UserRole` with `STUDENT = "STUDENT"`.
   - Add nullable `student_id = Column(Integer, ForeignKey("students.id"), nullable=True)` to `User` model, linking a login account directly to an enrolled `Student` record.
   - Alternatively, support student login via `register_number` and password.
2. **`Timetable` (`timetables`)**:
   - Fields: `id`, `class_id`, `subject_id`, `teacher_id`, `day_of_week` (Monday–Saturday), `period_number`, `start_time`, `end_time`, `room_number`.
3. **`Assignment` (`assignments`)**:
   - Fields: `id`, `title`, `description`, `class_id`, `subject_id`, `teacher_id`, `due_date`, `max_marks`, `attachment_path`, `created_at`.
4. **`AssignmentSubmission` (`assignment_submissions`)**:
   - Fields: `id`, `assignment_id`, `student_id`, `submission_text`, `file_path`, `submitted_at`, `marks_obtained`, `feedback`, `status` (`SUBMITTED`, `GRADED`, `LATE`).
5. **`Grade` / `InternalMark` (`grades`)**:
   - Fields: `id`, `student_id`, `subject_id`, `exam_type` (Internal 1, Internal 2, Midterm, Semester, Practical), `max_marks`, `marks_obtained`, `remarks`, `recorded_by_teacher_id`, `created_at`.
6. **`Announcement` / `Notice` (`announcements`)**:
   - Fields: `id`, `title`, `content`, `target_role` (`ALL`, `STUDENTS`, `TEACHERS`), `target_class_id` (optional), `priority` (`NORMAL`, `URGENT`), `posted_by_user_id`, `created_at`.

---

### 5.2 New API Endpoints

#### A. Student Portal (`/api/v1/student-portal/`)
- `GET /student-portal/me`: Current student profile, class info, face enrollment status.
- `GET /student-portal/attendance`: Personal attendance breakdown (overall %, subject-wise %, monthly summary, 75% low attendance warning).
- `GET /student-portal/timetable`: Weekly timetable for the student's assigned class.
- `GET /student-portal/assignments`: List of assignments for enrolled subjects (pending, submitted, evaluated).
- `POST /student-portal/assignments/{id}/submit`: Submit text or file for an assignment.
- `GET /student-portal/grades`: Internal assessment marks and performance reports.
- `GET /student-portal/announcements`: Class and institutional notices.

#### B. Extended Teacher Portal (`/api/v1/teacher-portal/`)
- `GET /teacher-portal/timetable`: Weekly teaching schedule across assigned subjects/sections.
- `GET / POST / PUT / DELETE /teacher-portal/assignments`: Create and manage course assignments.
- `GET /teacher-portal/assignments/{id}/submissions`: View submitted work from students.
- `POST /teacher-portal/assignments/{id}/grade`: Assign marks and qualitative feedback.
- `GET / POST / PUT /teacher-portal/grades`: Enter and update student test and internal marks.
- `GET / POST /teacher-portal/announcements`: Broadcast announcements to classes.

---

### 5.3 Frontend Portal Enhancements

1. **Role Gating in `index.html` and `app.js`**:
   - Update `data-role-req` so students only see:
     * Student Dashboard (Overview, Attendance %, Schedule, Assignments, Marks, Notices).
     * Profile & Enrollment status.
   - Teachers continue having access to:
     * One-Click Attendance capture.
     * Class Teacher / Subject Teacher portals.
     * New: Assignment Manager, Gradebook, Schedule, and Notice Composer.
   - Admin continues having institution-wide access.
2. **Dedicated Student Portal View (`student-portal-section`)**:
   - **Hero Metric Tiles**: Overall Attendance %, Pending Assignments, Upcoming Tests, Recent Notices.
   - **Attendance Progress Gauge**: Visual indicator showing distance to the 75% mandatory threshold.
   - **Interactive Timetable Matrix**: Clean grid showing Monday–Saturday period schedule.
   - **Assignment Submission Modal**: Upload file or type solution with real-time status.
   - **Academic Transcript Table**: Subject-wise scores with grading metrics.

---

## 6. Migration Risks & Safeguards

| Potential Risk | Impact | Mitigation / Safeguard |
|---|---|---|
| **Breaking Existing Attendance Engine** | High | **Zero changes** to `face_service.py`, `face_recognition.py`, OpenCV weights, or `/attendance/analyze` / `/confirm` workflows. |
| **Existing Database Integrity** | High | Do **NOT** replace or drop `attendance.db`. New tables (`timetables`, `assignments`, `grades`, `announcements`) will be created via SQLAlchemy `Base.metadata.create_all(bind=engine)` which is purely additive and non-destructive. |
| **User Role Compatibility** | Medium | Extending `UserRole` with `STUDENT` without altering existing enum records (`ADMIN`, `CLASS_TEACHER`, `SUBJECT_TEACHER`). Existing demo credentials (`admin/admin123`, `sharma/teacher123`, `patel/teacher123`) remain untouched. |
| **Frontend Navigation Conflicts** | Medium | Isolate student views under a dedicated `student-portal-section` and refine `data-role-req` attributes to prevent unauthorized menu exposure. |
| **File Storage Conflicts** | Low | Store assignment submissions in `data/assignments/` and notices in `data/notices/`, leaving `data/faces/` and `data/attendance_photos/` isolated. |

---

## 7. Phased Implementation Roadmap

1. **Phase 1: Database & Backend Schemas (Additive Only)**
   - Add models: `Timetable`, `Assignment`, `AssignmentSubmission`, `Grade`, `Announcement`.
   - Update `UserRole` to support `STUDENT` and add `student_id` relation to `User`.
   - Run `Base.metadata.create_all` safely to generate new tables without touching existing data.
2. **Phase 2: Core Endpoints for Student & Extended Teacher Portals**
   - Implement `/api/v1/student-portal/*` routes.
   - Implement `/api/v1/teacher-portal/*` routes.
   - Add student user seed data linked to existing students (e.g. `student1 / student123`).
3. **Phase 3: Frontend UI Expansion**
   - Add `student-portal-section` in `index.html`.
   - Add teacher assignment/grade/timetable tabs in existing teacher views.
   - Update `app.js` and `api.js` to handle student dashboard state and role routing.
4. **Phase 4: Verification & Regression Testing**
   - Run existing live tests (`test_dash_filters.py`, `backend/tests/*`) to verify that the CV attendance engine, admin portal, and teacher portals operate flawlessly.
   - Validate student login and end-to-end coursework submission flow.
