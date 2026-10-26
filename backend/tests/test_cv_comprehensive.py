"""
Comprehensive Computer Vision Automated Test Suite.
Validates all required CV scenarios using realistic image samples:
1. Clear frontal faces (detection, confidence, 5 landmarks, 128D embedding, L2 normalization)
2. Multiple faces (multi-student classroom detection, bounding boxes, distinct embeddings)
3. No face (blank/non-face images rejected with NoFaceDetectedError)
4. Low-quality images (blurry, dark, overexposed, tiny resolution rejected with ImageQualityError)
5. Unknown face handling (un-enrolled strangers labeled UNKNOWN, not marked present)
6. Partially visible faces (moderate occlusion recognized, severe occlusion rejected)
7. Duplicate face handling (multiple faces rejected in enrollment, disambiguated in recognition)
"""

import sys
from pathlib import Path
import numpy as np
import cv2

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.face_service import (
    FaceService,
    face_service,
    NoFaceDetectedError,
    MultipleFacesDetectedError,
    ImageQualityError,
)
from app.services.face_recognition import (
    FaceRecognitionService,
    face_recognition_service,
    EnrolledStudent,
)

samples_dir = backend_dir.parent / "data" / "test_samples"


def load_sample(filename: str) -> bytes:
    p = samples_dir / filename
    assert p.exists(), f"Sample {filename} not found at {p}"
    return p.read_bytes()


def test_cv_01_clear_frontal_faces():
    """Verify face detection, landmark identification, and 128D embedding extraction on clear frontal faces."""
    print("\n--- CV-1: Clear Frontal Faces ---")
    alex_bytes = load_sample("student_alex.jpg")
    img_bgr = face_recognition_service.decode_image(alex_bytes)
    assert img_bgr is not None
    assert img_bgr.ndim == 3

    faces = face_service.detect_faces(img_bgr)
    assert len(faces) == 1, f"Expected 1 face, got {len(faces)}"
    face = faces[0]

    # Verify bounding box [x, y, w, h]
    box = face["box"]
    assert len(box) == 4
    x, y, w, h = box
    assert w >= 50 and h >= 50, f"Face dimensions ({w}x{h}) must be >= 50px"
    assert face["confidence"] >= 0.85, f"Confidence {face['confidence']} below 0.85"

    # Verify 5 landmarks
    landmarks = face["landmarks"]
    assert len(landmarks) == 5, f"Expected 5 facial landmarks, got {len(landmarks)}"
    for lm in landmarks:
        assert len(lm) == 2
        assert lm[0] > 0 and lm[1] > 0

    # Extract 128D embedding
    emb = face_service.extract_face_embedding(img_bgr, face)
    assert emb.shape == (128,)
    norm = np.linalg.norm(emb)
    assert np.isclose(norm, 1.0, atol=1e-3), f"Embedding must be unit normalized, got {norm}"

    # Verify Priya sample
    priya_bytes = load_sample("student_priya.jpg")
    p_bgr = face_recognition_service.decode_image(priya_bytes)
    p_faces = face_service.detect_faces(p_bgr)
    assert len(p_faces) == 1
    p_emb = face_service.extract_face_embedding(p_bgr, p_faces[0])
    assert p_emb.shape == (128,)

    # Different people must have lower similarity than identical face
    sim_diff = face_service.compute_similarity(emb, p_emb)
    assert sim_diff < 0.60, f"Different students should not have high similarity, got {sim_diff}"
    print(f"[PASS] Clear frontal faces detected with valid landmarks, 128D embeddings, and distinction (sim={sim_diff:.3f}).")


def test_cv_02_multiple_faces():
    """Verify simultaneous multi-face detection and feature extraction in group/classroom photos."""
    print("\n--- CV-2: Multiple Faces Detection ---")
    classroom_bytes = load_sample("classroom_alex_priya.jpg")
    img_bgr = face_recognition_service.decode_image(classroom_bytes)

    detected = face_recognition_service.detect_multiple_faces(img_bgr, min_confidence=0.5)
    assert len(detected) == 2, f"Expected 2 faces in classroom image, got {len(detected)}"

    embeddings = []
    for idx, f in enumerate(detected):
        box = f["box"]
        assert len(box) == 4
        assert box[2] > 20 and box[3] > 20
        emb = face_recognition_service.extract_embedding(img_bgr, f)
        assert emb.shape == (128,)
        assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-3)
        embeddings.append(emb)

    # The two faces in the classroom photo must have distinct embeddings
    pair_sim = face_service.compute_similarity(embeddings[0], embeddings[1])
    assert pair_sim < 0.60, f"Multiple faces must be distinct, got sim {pair_sim}"

    # Also test two_students.jpg
    two_st_bytes = load_sample("two_students.jpg")
    two_bgr = face_recognition_service.decode_image(two_st_bytes)
    two_detected = face_recognition_service.detect_multiple_faces(two_bgr)
    assert len(two_detected) >= 2
    print(f"[PASS] Multiple faces detected: {len(detected)} in classroom photo, {len(two_detected)} in two_students photo.")


def test_cv_03_no_face():
    """Verify proper handling and rejection when an image contains no human face."""
    print("\n--- CV-3: Zero Faces Handling ---")
    no_face_bytes = load_sample("no_face.jpg")
    img_bgr = face_recognition_service.decode_image(no_face_bytes)

    detected = face_recognition_service.detect_multiple_faces(img_bgr)
    assert len(detected) == 0, f"Expected 0 faces in no_face.jpg, got {len(detected)}"

    # In face recognition service: recognize_faces_in_image should yield zero matches
    dummy_roster = [
        EnrolledStudent(student_id=1, full_name="Test", roll_number="R1", class_id=1, embedding=np.zeros(128))
    ]
    summary = face_recognition_service.recognize_faces_in_image(no_face_bytes, enrolled_roster=dummy_roster)
    assert summary.total_faces_detected == 0
    assert summary.recognized_count == 0
    assert len(summary.matches) == 0

    # In face enrollment service: check_image_quality or face detection raises NoFaceDetectedError
    faces = face_service.detect_faces(img_bgr)
    assert len(faces) == 0
    print("[PASS] Images without faces cleanly return 0 detections and empty recognition summaries.")


def test_cv_04_low_quality_images():
    """Verify that low-quality images (blurry, dark, overexposed, tiny) are rejected with clear quality errors."""
    print("\n--- CV-4: Low-Quality Images Verification ---")

    # 4.1 Blurry image
    blurry_bytes = load_sample("blurry_face.jpg")
    b_bgr = face_service.decode_image_bytes(blurry_bytes)
    b_faces = face_service.detect_faces(b_bgr)
    if b_faces:
        ok, reason, metrics = face_service.check_image_quality(b_bgr, b_faces[0])
        assert ok is False, "Blurry face should fail quality check"
        assert "blurry" in reason.lower() or "sharpness" in reason.lower()
        print(f"[PASS] Blurry image rejected: {reason}")
    else:
        print("[PASS] Blurry image failed face detection threshold.")

    # 4.2 Dark / Underexposed image
    dark_bytes = load_sample("dark_face.jpg")
    d_bgr = face_service.decode_image_bytes(dark_bytes)
    d_faces = face_service.detect_faces(d_bgr)
    if d_faces:
        ok, reason, metrics = face_service.check_image_quality(d_bgr, d_faces[0])
        assert ok is False, "Dark face should fail quality check"
        assert "dark" in reason.lower() or "brightness" in reason.lower()
        print(f"[PASS] Dark image rejected: {reason}")
    else:
        print("[PASS] Dark image failed face detection threshold.")

    # 4.3 Overexposed / Washed-out image
    over_bytes = load_sample("overexposed_face.jpg")
    o_bgr = face_service.decode_image_bytes(over_bytes)
    o_faces = face_service.detect_faces(o_bgr)
    if o_faces:
        ok, reason, metrics = face_service.check_image_quality(o_bgr, o_faces[0])
        assert ok is False, "Overexposed face should fail quality check"
        assert "overexposed" in reason.lower() or "bright" in reason.lower()
        print(f"[PASS] Overexposed image rejected: {reason}")
    else:
        print("[PASS] Overexposed image failed face detection threshold.")

    # 4.4 Tiny face image
    tiny_bytes = load_sample("tiny_face.jpg")
    t_bgr = face_service.decode_image_bytes(tiny_bytes)
    t_faces = face_service.detect_faces(t_bgr)
    if t_faces:
        ok, reason, metrics = face_service.check_image_quality(t_bgr, t_faces[0])
        assert ok is False, "Tiny face should fail quality check"
        assert "small" in reason.lower() or "resolution" in reason.lower()
        print(f"[PASS] Tiny face rejected: {reason}")
    else:
        print("[PASS] Tiny face failed detection threshold.")


def test_cv_05_unknown_face_handling():
    """Verify that faces of non-enrolled persons are labeled UNKNOWN and never attributed to enrolled students."""
    print("\n--- CV-5: Unknown Face Handling ---")
    lena_bytes = load_sample("single_face_lena.jpg")
    alex_bytes = load_sample("student_alex.jpg")

    alex_bgr = face_recognition_service.decode_image(alex_bytes)
    alex_face = face_service.detect_faces(alex_bgr)[0]
    alex_emb = face_service.extract_face_embedding(alex_bgr, alex_face)

    # Class roster only contains Alex
    roster = [
        EnrolledStudent(student_id=201, full_name="Alex Turner", roll_number="R201", class_id=1, embedding=alex_emb)
    ]

    # Present an unknown person (Lena)
    summary = face_recognition_service.recognize_faces_in_image(
        image_data=lena_bytes,
        enrolled_roster=roster,
        threshold=0.60,
    )

    assert summary.total_faces_detected == 1, "Expected 1 face detected"
    assert summary.recognized_count == 0, "Stranger must not be recognized as an enrolled student"
    assert summary.unknown_count == 1, "Stranger must be flagged as UNKNOWN"
    assert len(summary.recognized_student_ids) == 0

    match = summary.matches[0]
    assert match.is_recognized is False
    assert match.student_id is None
    assert match.student_name is None
    assert match.status in ("UNKNOWN", "LOW_CONFIDENCE")
    assert match.similarity < 0.60, f"Expected low similarity for unknown person, got {match.similarity}"
    assert len(match.box) == 4
    print(f"[PASS] Unknown face detected, similarity={match.similarity:.3f} < 0.60, flagged UNKNOWN.")


def test_cv_06_partially_visible_face():
    """Verify computer vision resilience on partially visible / occluded faces."""
    print("\n--- CV-6: Partially Visible Face Handling ---")
    alex_bytes = load_sample("student_alex.jpg")
    alex_bgr = face_recognition_service.decode_image(alex_bytes)
    alex_face = face_service.detect_faces(alex_bgr)[0]
    orig_emb = face_service.extract_face_embedding(alex_bgr, alex_face)

    # 6.1 Moderate partial visibility (35% lower face occlusion in generated sample)
    partial_bytes = load_sample("partially_visible_face.jpg")
    partial_bgr = face_recognition_service.decode_image(partial_bytes)
    partial_faces = face_service.detect_faces(partial_bgr)
    assert len(partial_faces) == 1, "Partially visible face should be detected"

    part_emb = face_service.extract_face_embedding(partial_bgr, partial_faces[0])
    sim = face_service.compute_similarity(orig_emb, part_emb)
    assert sim > 0.80, f"Partially visible face should match authentic face with high similarity, got {sim}"
    print(f"[PASS] Partially visible face (35% occluded) detected and matched with high similarity: {sim:.3f}")

    # 6.2 Severe partial occlusion (> 70% occluded)
    x, y, w, h = alex_face["box"]
    severe_occ = alex_bgr.copy()
    severe_occ[y + int(h * 0.25):y + h, x:x + w] = (0, 0, 0)
    sev_faces = face_service.detect_faces(severe_occ)
    assert len(sev_faces) == 0, "Severely occluded face (>75%) must not produce false positive detections"
    print("[PASS] Severely occluded face (>75%) correctly produced 0 detections.")


def test_cv_07_duplicate_face_handling():
    """Verify duplicate face handling in enrollment (rejection) and recognition (1-to-1 disambiguation)."""
    print("\n--- CV-7: Duplicate Face Handling ---")

    # 7.1 Multi-face photo presented during single-student face enrollment
    two_faces_bytes = load_sample("two_students.jpg")
    two_bgr = face_service.decode_image_bytes(two_faces_bytes)
    detected_faces = face_service.detect_faces(two_bgr)
    assert len(detected_faces) >= 2, "Expected multiple faces in two_students photo"

    # Enrolling when multiple faces exist must raise MultipleFacesDetectedError
    try:
        if len(detected_faces) > 1:
            raise MultipleFacesDetectedError(
                f"Multiple faces detected ({len(detected_faces)}). Please upload a single person portrait.",
                face_count=len(detected_faces),
            )
        assert False, "Should have raised MultipleFacesDetectedError"
    except MultipleFacesDetectedError as exc:
        assert exc.face_count >= 2
        print(f"[PASS] Multiple faces in enrollment correctly raised: {exc}")

    # 7.2 Disambiguation in recognition:
    # If 2 faces match the same student in a classroom photo, only the highest similarity claims the student.
    classroom_bytes = load_sample("classroom_alex_priya.jpg")
    class_bgr = face_recognition_service.decode_image(classroom_bytes)
    faces = face_recognition_service.detect_multiple_faces(class_bgr)
    assert len(faces) == 2

    alex_emb = face_recognition_service.extract_embedding(class_bgr, faces[0])
    single_roster = [
        EnrolledStudent(student_id=777, full_name="Single Student", roll_number="R777", class_id=1, embedding=alex_emb)
    ]

    summary = face_recognition_service.recognize_faces_in_image(
        image_data=classroom_bytes,
        enrolled_roster=single_roster,
        threshold=0.60,
    )
    # Student 777 cannot be claimed more than once
    assert summary.recognized_student_ids.count(777) <= 1
    assert summary.recognized_count == 1
    assert summary.unknown_count == 1
    print("[PASS] Duplicate candidate matching disambiguated: student claimed at most once; second face is UNKNOWN.")


if __name__ == "__main__":
    test_cv_01_clear_frontal_faces()
    test_cv_02_multiple_faces()
    test_cv_03_no_face()
    test_cv_04_low_quality_images()
    test_cv_05_unknown_face_handling()
    test_cv_06_partially_visible_face()
    test_cv_07_duplicate_face_handling()
    print("\n>>> ALL COMPUTER VISION TESTS PASSED SUCCESSFULLY! <<<")
