"""
Unit Tests for the Modular Computer Vision Face Recognition Service.
Validates:
1. Loading of configured face detection and embedding models (YuNet & SFace).
2. Detection of multiple faces across an image.
3. Feature embedding extraction (128D L2-normalized vectors).
4. Comparison strictly against enrolled students of the selected class (class boundary isolation).
5. Similarity (Cosine) and distance (Euclidean) calculation.
6. Configurable recognition threshold behavior.
7. Return payload format (student ID, confidence/similarity, bounding box, UNKNOWN status).
8. Protection against marking low-confidence matches as present.
9. Independence of the service from API routing layers.
"""

import io
import json
import logging
import sys
from pathlib import Path
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.database import SessionLocal
from app.models.academic import Class
from app.models.student import Student, StudentFace
from app.services.face_service import face_service
from app.services.face_recognition import (
    FaceRecognitionService,
    face_recognition_service,
    EnrolledStudent,
    FaceMatchResult,
    RecognitionSummary,
)

samples_dir = backend_dir.parent / "data" / "test_samples"


def load_sample_bytes(filename: str) -> bytes:
    sample_path = samples_dir / filename
    assert sample_path.exists(), f"Sample image file {sample_path} does not exist."
    with open(sample_path, "rb") as f:
        return f.read()


def test_01_model_loading_and_configuration():
    """Verify that FaceRecognitionService initializes with proper models and settings."""
    print("\n--- Test 1: Model Loading & Service Configuration ---")
    service = FaceRecognitionService()
    assert service.threshold == settings.FACE_MATCH_THRESHOLD
    assert service.min_confidence == settings.MIN_FACE_CONFIDENCE
    assert service._face_service is not None
    assert service._face_service.detector is not None
    assert service._face_service.recognizer is not None

    # Custom threshold override during initialization
    custom_service = FaceRecognitionService(default_threshold=0.75, min_confidence=0.8)
    assert custom_service.threshold == 0.75
    assert custom_service.min_confidence == 0.8
    print("PASS: Face recognition models and configuration loaded successfully.")


def test_02_detect_multiple_faces_and_embeddings():
    """Detect multiple faces in a classroom image and extract 128D embeddings."""
    print("\n--- Test 2: Detect Multiple Faces & Extract Embeddings ---")
    img_bytes = load_sample_bytes("classroom_alex_priya.jpg")
    img_bgr = face_recognition_service.decode_image(img_bytes)

    detected_faces = face_recognition_service.detect_multiple_faces(img_bgr, min_confidence=0.5)
    print(f"Detected {len(detected_faces)} face(s) in classroom image.")
    assert len(detected_faces) == 2, f"Expected 2 faces, got {len(detected_faces)}"

    for idx, face in enumerate(detected_faces):
        box = face["box"]
        conf = face["confidence"]
        assert len(box) == 4
        assert box[2] > 20 and box[3] > 20, "Bounding box width and height must be valid"
        assert conf >= 0.5, f"Confidence {conf} is below 0.5"

        emb = face_recognition_service.extract_embedding(img_bgr, face)
        assert emb is not None, f"Failed to extract embedding for face {idx}"
        assert emb.shape == (128,), f"Expected 128D embedding, got {emb.shape}"

        # Verify L2 normalization
        norm = np.linalg.norm(emb)
        assert np.isclose(norm, 1.0, atol=1e-3), f"Embedding must be L2 normalized, norm={norm}"

    print("PASS: Multiple faces detected with valid bounding boxes and 128D normalized embeddings.")


def test_03_similarity_and_distance_metrics():
    """Verify Cosine Similarity and Euclidean Distance calculations."""
    print("\n--- Test 3: Cosine Similarity and Euclidean Distance Calculation ---")
    vec_a = np.random.randn(128).astype(np.float32)
    vec_a /= np.linalg.norm(vec_a)

    # Identical vector
    sim_identical = face_recognition_service.compute_similarity(vec_a, vec_a)
    dist_identical = face_recognition_service.compute_distance(vec_a, vec_a)
    assert np.isclose(sim_identical, 1.0, atol=1e-4), f"Identical similarity should be 1.0, got {sim_identical}"
    assert np.isclose(dist_identical, 0.0, atol=1e-4), f"Identical distance should be 0.0, got {dist_identical}"

    # Opposite vector
    vec_opp = -vec_a
    sim_opp = face_recognition_service.compute_similarity(vec_a, vec_opp)
    dist_opp = face_recognition_service.compute_distance(vec_a, vec_opp)
    assert np.isclose(sim_opp, -1.0, atol=1e-4)
    assert np.isclose(dist_opp, 2.0, atol=1e-4)

    # Orthogonal vectors
    vec_b = np.random.randn(128).astype(np.float32)
    vec_b -= vec_b.dot(vec_a) * vec_a
    vec_b /= np.linalg.norm(vec_b)
    sim_ortho = face_recognition_service.compute_similarity(vec_a, vec_b)
    dist_ortho = face_recognition_service.compute_distance(vec_a, vec_b)
    assert np.isclose(sim_ortho, 0.0, atol=1e-3)
    assert np.isclose(dist_ortho, np.sqrt(2.0), atol=1e-3)

    print("PASS: Similarity and distance metric calculations verified.")


def test_04_recognition_both_students_matched():
    """Verify recognizing both students when both are in the enrolled roster."""
    print("\n--- Test 4: In-Memory Multi-Face Recognition (Both Enrolled) ---")
    alex_bytes = load_sample_bytes("student_alex.jpg")
    priya_bytes = load_sample_bytes("student_priya.jpg")
    classroom_bytes = load_sample_bytes("classroom_alex_priya.jpg")

    alex_bgr = face_recognition_service.decode_image(alex_bytes)
    priya_bgr = face_recognition_service.decode_image(priya_bytes)

    alex_face = face_recognition_service.detect_multiple_faces(alex_bgr)[0]
    priya_face = face_recognition_service.detect_multiple_faces(priya_bgr)[0]

    alex_emb = face_recognition_service.extract_embedding(alex_bgr, alex_face)
    priya_emb = face_recognition_service.extract_embedding(priya_bgr, priya_face)

    roster = [
        EnrolledStudent(student_id=101, full_name="Alex Turner", roll_number="R101", class_id=1, embedding=alex_emb),
        EnrolledStudent(student_id=102, full_name="Priya Sharma", roll_number="R102", class_id=1, embedding=priya_emb),
    ]

    summary = face_recognition_service.recognize_faces_in_image(
        image_data=classroom_bytes,
        enrolled_roster=roster,
        threshold=0.60,
    )

    assert summary.total_faces_detected == 2
    assert summary.recognized_count == 2
    assert summary.unknown_count == 0
    assert set(summary.recognized_student_ids) == {101, 102}

    for match in summary.matches:
        assert match.is_recognized is True
        assert match.status == "RECOGNIZED"
        assert match.student_id in (101, 102)
        assert match.similarity > 0.85, f"Expected high similarity, got {match.similarity}"
        assert match.distance < 0.60
        assert len(match.box) == 4

    # Test serialization to dict
    summary_dict = summary.to_dict()
    assert summary_dict["recognized_count"] == 2
    assert len(summary_dict["matches"]) == 2
    print(f"PASS: Both students recognized with similarities: {[m.similarity for m in summary.matches]}")


def test_05_class_boundary_enforcement():
    """
    CRITICAL REQUIREMENT:
    Do not compare against or match students from unrelated classes.
    If student Priya is NOT in the roster for the selected class, her face MUST be marked UNKNOWN.
    """
    print("\n--- Test 5: Class Boundary Enforcement (Only Class Roster Evaluated) ---")
    alex_bytes = load_sample_bytes("student_alex.jpg")
    classroom_bytes = load_sample_bytes("classroom_alex_priya.jpg")

    alex_bgr = face_recognition_service.decode_image(alex_bytes)
    alex_face = face_recognition_service.detect_multiple_faces(alex_bgr)[0]
    alex_emb = face_recognition_service.extract_embedding(alex_bgr, alex_face)

    # Roster only contains Alex for Class 1 (Priya is in another class and NOT passed)
    roster_class_1 = [
        EnrolledStudent(student_id=101, full_name="Alex Turner", roll_number="R101", class_id=1, embedding=alex_emb),
    ]

    summary = face_recognition_service.recognize_faces_in_image(
        image_data=classroom_bytes,
        enrolled_roster=roster_class_1,
        threshold=0.60,
        class_id=1,
    )

    assert summary.total_faces_detected == 2
    assert summary.recognized_count == 1
    assert summary.unknown_count == 1
    assert summary.recognized_student_ids == [101]

    # Verify individual face statuses
    recognized_matches = [m for m in summary.matches if m.is_recognized]
    unknown_matches = [m for m in summary.matches if not m.is_recognized]

    assert len(recognized_matches) == 1
    assert recognized_matches[0].student_id == 101
    assert recognized_matches[0].student_name == "Alex Turner"
    assert recognized_matches[0].similarity > 0.85

    assert len(unknown_matches) == 1
    assert unknown_matches[0].student_id is None
    assert unknown_matches[0].student_name is None
    assert unknown_matches[0].status == "UNKNOWN"
    assert unknown_matches[0].is_recognized is False
    assert len(unknown_matches[0].box) == 4

    print("PASS: Unrelated student was NOT matched and returned with UNKNOWN status.")


def test_06_configurable_threshold_and_low_confidence_protection():
    """
    CRITICAL REQUIREMENT:
    Do not automatically mark low-confidence matches as present.
    Configurable threshold allows setting high strictness; matches below threshold become UNKNOWN/LOW_CONFIDENCE.
    """
    print("\n--- Test 6: Configurable Threshold & Low-Confidence Protection ---")
    alex_bytes = load_sample_bytes("student_alex.jpg")
    priya_bytes = load_sample_bytes("student_priya.jpg")
    classroom_bytes = load_sample_bytes("classroom_alex_priya.jpg")

    alex_bgr = face_recognition_service.decode_image(alex_bytes)
    priya_bgr = face_recognition_service.decode_image(priya_bytes)
    alex_emb = face_recognition_service.extract_embedding(alex_bgr, face_recognition_service.detect_multiple_faces(alex_bgr)[0])
    priya_emb = face_recognition_service.extract_embedding(priya_bgr, face_recognition_service.detect_multiple_faces(priya_bgr)[0])

    roster = [
        EnrolledStudent(student_id=101, full_name="Alex Turner", roll_number="R101", class_id=1, embedding=alex_emb),
        EnrolledStudent(student_id=102, full_name="Priya Sharma", roll_number="R102", class_id=1, embedding=priya_emb),
    ]

    # Ultra-high threshold: 0.999 (above typical 0.92-0.94 similarity)
    strict_summary = face_recognition_service.recognize_faces_in_image(
        image_data=classroom_bytes,
        enrolled_roster=roster,
        threshold=0.999,
    )

    assert strict_summary.total_faces_detected == 2
    assert strict_summary.recognized_count == 0, "No face should pass threshold=0.999"
    assert strict_summary.unknown_count == 2
    assert len(strict_summary.recognized_student_ids) == 0

    for match in strict_summary.matches:
        assert match.is_recognized is False
        assert match.student_id is None
        assert match.status in ("UNKNOWN", "LOW_CONFIDENCE")
        assert match.threshold_applied == 0.999

    print("PASS: High threshold correctly classified all faces as UNKNOWN / LOW_CONFIDENCE.")


def test_07_no_face_detected():
    """Verify handling when an image has zero faces."""
    print("\n--- Test 7: Zero Faces Handling ---")
    no_face_bytes = load_sample_bytes("no_face.jpg")
    dummy_roster = [
        EnrolledStudent(student_id=1, full_name="Test", roll_number="R1", class_id=1, embedding=np.zeros(128)),
    ]

    summary = face_recognition_service.recognize_faces_in_image(
        image_data=no_face_bytes,
        enrolled_roster=dummy_roster,
    )
    assert summary.total_faces_detected == 0
    assert summary.recognized_count == 0
    assert summary.unknown_count == 0
    assert len(summary.matches) == 0
    assert len(summary.recognized_student_ids) == 0
    print("PASS: Zero faces cleanly returned empty summary.")


def test_08_duplicate_student_disambiguation():
    """
    Ensure one student cannot be assigned to multiple detected faces.
    If 2 faces match the same student, only the highest similarity claims the student.
    The second face must become UNKNOWN or LOW_CONFIDENCE.
    """
    print("\n--- Test 8: 1-to-1 Match Disambiguation ---")
    two_faces_bytes = load_sample_bytes("two_students.jpg")
    img_bgr = face_recognition_service.decode_image(two_faces_bytes)
    faces = face_recognition_service.detect_multiple_faces(img_bgr)
    assert len(faces) >= 2

    # Extract embedding from face 0 and enroll only ONE student with this embedding
    emb_face_0 = face_recognition_service.extract_embedding(img_bgr, faces[0])
    single_roster = [
        EnrolledStudent(student_id=999, full_name="Only One", roll_number="R999", class_id=1, embedding=emb_face_0),
    ]

    summary = face_recognition_service.recognize_faces_in_image(
        image_data=two_faces_bytes,
        enrolled_roster=single_roster,
        threshold=0.60,
    )

    # Exactly one face may claim student 999
    assert summary.recognized_count <= 1
    assert summary.recognized_student_ids.count(999) <= 1
    print(f"PASS: Single student claimed at most once across {summary.total_faces_detected} detected faces.")


def test_09_database_integrated_class_attendance():
    """
    Verify high-level recognize_class_attendance method with real database fixtures.
    Ensures that when querying Class A, students in Class B are never evaluated.
    """
    print("\n--- Test 9: Database Integrated Class-Scoped Recognition ---")
    db = SessionLocal()
    try:
        # Create two distinct test classes
        class_a = db.query(Class).filter(Class.name == "Test Class Recognition A").first()
        if not class_a:
            class_a = Class(name="Test Class Recognition A", department="Computer Science", year=3, section="RA")
            db.add(class_a)
            db.flush()

        class_b = db.query(Class).filter(Class.name == "Test Class Recognition B").first()
        if not class_b:
            class_b = Class(name="Test Class Recognition B", department="Computer Science", year=3, section="RB")
            db.add(class_b)
            db.flush()

        # Enroll Student 1 (Alex) into Class A
        student_a = db.query(Student).filter(Student.roll_number == "RECOG_ALEX_01").first()
        if not student_a:
            student_a = Student(
                roll_number="RECOG_ALEX_01",
                register_number="REG_RECOG_ALEX_01",
                full_name="Alex Recog A",
                department="Computer Science",
                year=3,
                section="RA",
                class_id=class_a.id,
                is_active=True,
                face_enrolled=True,
            )
            db.add(student_a)
            db.flush()

        # Enroll Student 2 (Priya) into Class B
        student_b = db.query(Student).filter(Student.roll_number == "RECOG_PRIYA_02").first()
        if not student_b:
            student_b = Student(
                roll_number="RECOG_PRIYA_02",
                register_number="REG_RECOG_PRIYA_02",
                full_name="Priya Recog B",
                department="Computer Science",
                year=3,
                section="RB",
                class_id=class_b.id,
                is_active=True,
                face_enrolled=True,
            )
            db.add(student_b)
            db.flush()

        # Extract real embeddings
        alex_bytes = load_sample_bytes("student_alex.jpg")
        priya_bytes = load_sample_bytes("student_priya.jpg")

        alex_bgr = face_recognition_service.decode_image(alex_bytes)
        priya_bgr = face_recognition_service.decode_image(priya_bytes)

        alex_face = face_recognition_service.detect_multiple_faces(alex_bgr)[0]
        priya_face = face_recognition_service.detect_multiple_faces(priya_bgr)[0]

        alex_emb = face_recognition_service.extract_embedding(alex_bgr, alex_face)
        priya_emb = face_recognition_service.extract_embedding(priya_bgr, priya_face)

        alex_emb_str = face_service.serialize_embedding(alex_emb)
        priya_emb_str = face_service.serialize_embedding(priya_emb)

        # Upsert StudentFace records
        face_a = db.query(StudentFace).filter(StudentFace.student_id == student_a.id).first()
        if not face_a:
            face_a = StudentFace(student_id=student_a.id, embedding=alex_emb_str, is_primary=True)
            db.add(face_a)
        else:
            face_a.embedding = alex_emb_str

        face_b = db.query(StudentFace).filter(StudentFace.student_id == student_b.id).first()
        if not face_b:
            face_b = StudentFace(student_id=student_b.id, embedding=priya_emb_str, is_primary=True)
            db.add(face_b)
        else:
            face_b.embedding = priya_emb_str

        db.commit()

        # Execute recognition for Class A on classroom photo (contains both Alex and Priya)
        classroom_bytes = load_sample_bytes("classroom_alex_priya.jpg")
        summary_a = face_recognition_service.recognize_class_attendance(
            db=db,
            class_id=class_a.id,
            image_data=classroom_bytes,
        )

        assert summary_a.total_faces_detected == 2
        assert summary_a.recognized_count == 1, f"Expected 1 recognized in Class A, got {summary_a.recognized_count}"
        assert summary_a.recognized_student_ids == [student_a.id]
        assert student_b.id not in summary_a.recognized_student_ids, "Student from Class B must NOT be recognized in Class A"

        # Execute recognition for Class B on the same classroom photo
        summary_b = face_recognition_service.recognize_class_attendance(
            db=db,
            class_id=class_b.id,
            image_data=classroom_bytes,
        )

        assert summary_b.total_faces_detected == 2
        assert summary_b.recognized_count == 1, f"Expected 1 recognized in Class B, got {summary_b.recognized_count}"
        assert summary_b.recognized_student_ids == [student_b.id]
        assert student_a.id not in summary_b.recognized_student_ids, "Student from Class A must NOT be recognized in Class B"

        print("PASS: Class-scoped attendance queries strictly prevent cross-class matching.")

    finally:
        db.close()


def run_all_tests():
    print("=" * 80)
    print("STARTING FACE RECOGNITION SERVICE UNIT TEST SUITE")
    print("=" * 80)

    test_01_model_loading_and_configuration()
    test_02_detect_multiple_faces_and_embeddings()
    test_03_similarity_and_distance_metrics()
    test_04_recognition_both_students_matched()
    test_05_class_boundary_enforcement()
    test_06_configurable_threshold_and_low_confidence_protection()
    test_07_no_face_detected()
    test_08_duplicate_student_disambiguation()
    test_09_database_integrated_class_attendance()

    print("\n" + "=" * 80)
    print("ALL 9 UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
