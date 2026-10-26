"""
Computer Vision Face Recognition Service.
Handles multi-face detection, feature embedding extraction, and class-scoped
facial recognition against enrolled student vectors.

Key Features:
1. Loads configured OpenCV YuNet detector and SFace recognizer models.
2. Detects multiple student faces across wide classroom photographs.
3. Generates 128D normalized feature embeddings for all detected faces.
4. Restricts matching strictly to enrolled students of the selected class.
5. Calculates Cosine Similarity and Euclidean Distance against enrolled vectors.
6. Applies configurable recognition threshold (defaults to settings.FACE_MATCH_THRESHOLD).
7. Returns structured match results with student ID, confidence, bounding boxes,
   and explicit 'UNKNOWN' status when no reliable match exists.
8. Decoupled from HTTP / API routing layers for standalone modularity and unit testing.
"""

from dataclasses import dataclass, field
import io
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.services.face_service import face_service, FaceService

logger = logging.getLogger("one-click-attendance.face_recognition")


@dataclass
class EnrolledStudent:
    """Enrolled student metadata and facial feature vector."""
    student_id: int
    full_name: str
    roll_number: str
    class_id: int
    embedding: np.ndarray

    def __post_init__(self):
        # Ensure embedding is a 1D float32 normalized numpy array
        if not isinstance(self.embedding, np.ndarray):
            self.embedding = np.array(self.embedding, dtype=np.float32)
        else:
            self.embedding = self.embedding.astype(np.float32)
        norm = np.linalg.norm(self.embedding)
        if norm > 1e-6:
            self.embedding = self.embedding / norm


@dataclass
class FaceMatchResult:
    """Recognition result for an individual detected face."""
    box: List[int]                     # [x, y, w, h] bounding box
    detection_confidence: float        # YuNet face detector confidence
    is_recognized: bool                # True if matched above threshold
    status: str                        # "RECOGNIZED" | "UNKNOWN" | "LOW_CONFIDENCE"
    student_id: Optional[int] = None   # Matched student ID if recognized, else None
    student_name: Optional[str] = None # Matched student name if recognized, else None
    roll_number: Optional[str] = None  # Matched student roll number if recognized, else None
    similarity: float = 0.0            # Cosine similarity score [-1.0, 1.0]
    distance: float = 0.0              # Euclidean distance (lower is closer)
    threshold_applied: float = 0.60    # Threshold used for this decision
    landmarks: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "box": self.box,
            "detection_confidence": round(self.detection_confidence, 4),
            "is_recognized": self.is_recognized,
            "status": self.status,
            "student_id": self.student_id,
            "student_name": self.student_name,
            "roll_number": self.roll_number,
            "similarity": round(self.similarity, 4),
            "distance": round(self.distance, 4),
            "threshold_applied": round(self.threshold_applied, 4),
        }


@dataclass
class RecognitionSummary:
    """Summary of facial recognition performed on an image."""
    class_id: Optional[int]
    total_faces_detected: int
    recognized_count: int
    unknown_count: int
    threshold: float
    matches: List[FaceMatchResult]
    recognized_student_ids: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "total_faces_detected": self.total_faces_detected,
            "recognized_count": self.recognized_count,
            "unknown_count": self.unknown_count,
            "threshold": self.threshold,
            "matches": [m.to_dict() for m in self.matches],
            "recognized_student_ids": self.recognized_student_ids,
        }


class FaceRecognitionService:
    """
    Computer Vision Face Recognition Service.
    Compares detected faces in classroom group photos exclusively against
    the enrolled student vectors of a designated class.
    """

    def __init__(
        self,
        default_threshold: Optional[float] = None,
        min_confidence: Optional[float] = None,
        face_svc: Optional[FaceService] = None,
    ):
        self.threshold = (
            default_threshold
            if default_threshold is not None
            else settings.FACE_MATCH_THRESHOLD
        )
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else settings.MIN_FACE_CONFIDENCE
        )
        self._face_service = face_svc or face_service

    def decode_image(self, image_data: Union[bytes, np.ndarray]) -> np.ndarray:
        """Decodes raw bytes into BGR numpy array, or returns existing numpy array."""
        if isinstance(image_data, np.ndarray):
            return image_data
        return self._face_service.decode_image_bytes(image_data)

    def detect_multiple_faces(
        self,
        img_bgr: np.ndarray,
        min_confidence: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detects all student faces present in a classroom image using YuNet.
        Returns list of face dicts with 'box', 'confidence', 'landmarks', 'raw'.
        """
        conf = min_confidence if min_confidence is not None else self.min_confidence
        return self._face_service.detect_faces(img_bgr, min_confidence=conf)

    def extract_embedding(
        self,
        img_bgr: np.ndarray,
        face_info: Dict[str, Any],
    ) -> Optional[np.ndarray]:
        """Extracts 128D normalized feature embedding using SFace."""
        try:
            return self._face_service.extract_face_embedding(img_bgr, face_info)
        except Exception as exc:
            logger.warning(f"Could not extract embedding for face at box {face_info.get('box')}: {exc}")
            return None

    def compute_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """
        Computes Cosine Similarity between two 128D normalized vectors.
        Returns float in range [-1.0, 1.0].
        """
        return self._face_service.compute_similarity(emb_a, emb_b)

    def compute_distance(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """
        Computes Euclidean distance between two 128D vectors.
        For normalized vectors: dist = sqrt(2 - 2 * cos_sim).
        """
        if emb_a is None or emb_b is None or len(emb_a) == 0 or len(emb_b) == 0:
            return float("inf")
        return float(np.linalg.norm(emb_a - emb_b))

    def load_enrolled_students_for_class(
        self,
        db: Session,
        class_id: int,
    ) -> List[EnrolledStudent]:
        """
        Queries and loads enrolled student embeddings EXCLUSIVELY for the given class_id.
        CRITICAL: Never compares against students from other classes.
        """
        from app.models.student import Student, StudentFace

        records = (
            db.query(Student, StudentFace)
            .join(StudentFace, StudentFace.student_id == Student.id)
            .filter(
                Student.class_id == class_id,
                Student.is_active == True,
                Student.face_enrolled == True,
                StudentFace.is_primary == True,
            )
            .all()
        )

        roster: List[EnrolledStudent] = []
        for st, face in records:
            if not face.embedding or face.embedding.strip() == "":
                continue
            try:
                emb_vec = self._face_service.deserialize_embedding(face.embedding)
                if len(emb_vec) == 128:
                    roster.append(
                        EnrolledStudent(
                            student_id=st.id,
                            full_name=st.full_name,
                            roll_number=st.roll_number,
                            class_id=st.class_id,
                            embedding=emb_vec,
                        )
                    )
            except Exception as exc:
                logger.warning(f"Failed to deserialize embedding for student {st.id}: {exc}")

        logger.info(
            f"Loaded {len(roster)} enrolled student embedding(s) exclusively for class_id={class_id}."
        )
        return roster

    def recognize_faces_in_image(
        self,
        image_data: Union[bytes, np.ndarray],
        enrolled_roster: List[EnrolledStudent],
        threshold: Optional[float] = None,
        min_confidence: Optional[float] = None,
        class_id: Optional[int] = None,
    ) -> RecognitionSummary:
        """
        Decoupled recognition engine:
        1. Detects all faces in image.
        2. Generates 128D embedding for every detected face.
        3. Compares each detected face against the provided enrolled_roster.
        4. Applies threshold: matches >= threshold are RECOGNIZED; < threshold are UNKNOWN.
        5. Disambiguates duplicate student matches to prevent multi-assignments.
        """
        effective_threshold = threshold if threshold is not None else self.threshold
        effective_min_conf = min_confidence if min_confidence is not None else self.min_confidence

        img_bgr = self.decode_image(image_data)
        detected_faces = self.detect_multiple_faces(img_bgr, min_confidence=effective_min_conf)
        total_detected = len(detected_faces)
        logger.info(f"Recognition pipeline: detected {total_detected} face(s) in image.")

        if total_detected == 0:
            return RecognitionSummary(
                class_id=class_id,
                total_faces_detected=0,
                recognized_count=0,
                unknown_count=0,
                threshold=effective_threshold,
                matches=[],
                recognized_student_ids=[],
            )

        # Step A: Compute similarity & distance for every detected face against all enrolled students
        # Store candidate matches: list of (face_index, best_student, best_sim, best_dist)
        candidates: List[Dict[str, Any]] = []

        for idx, face in enumerate(detected_faces):
            box = face["box"]
            det_conf = face["confidence"]
            landmarks = face.get("landmarks")

            emb = self.extract_embedding(img_bgr, face)
            if emb is None:
                candidates.append({
                    "face_index": idx,
                    "box": box,
                    "detection_confidence": det_conf,
                    "landmarks": landmarks,
                    "best_student": None,
                    "similarity": 0.0,
                    "distance": float("inf"),
                    "status": "UNKNOWN",
                })
                continue

            best_student: Optional[EnrolledStudent] = None
            best_sim = -1.0
            best_dist = float("inf")

            for enrolled in enrolled_roster:
                sim = self.compute_similarity(emb, enrolled.embedding)
                dist = self.compute_distance(emb, enrolled.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_dist = dist
                    best_student = enrolled

            candidates.append({
                "face_index": idx,
                "box": box,
                "detection_confidence": det_conf,
                "landmarks": landmarks,
                "best_student": best_student,
                "similarity": best_sim if best_sim != -1.0 else 0.0,
                "distance": best_dist,
                "status": "RECOGNIZED" if (best_student and best_sim >= effective_threshold) else "UNKNOWN",
            })

        # Step B: Disambiguate duplicate student assignments (1-to-1 match resolution)
        # If multiple detected faces match the same student above threshold, assign to highest similarity face only
        assigned_student_ids = set()
        # Sort candidates descending by similarity so strongest match claims the student first
        sorted_indices = sorted(
            range(len(candidates)),
            key=lambda i: candidates[i]["similarity"],
            reverse=True,
        )

        match_results: List[Optional[FaceMatchResult]] = [None] * len(candidates)
        recognized_ids: List[int] = []

        for i in sorted_indices:
            cand = candidates[i]
            student = cand["best_student"]
            sim = cand["similarity"]
            dist = cand["distance"]
            box = cand["box"]
            det_conf = cand["detection_confidence"]
            landmarks = cand["landmarks"]

            if student is not None and sim >= effective_threshold and student.student_id not in assigned_student_ids:
                # Valid match meeting threshold and not yet claimed
                assigned_student_ids.add(student.student_id)
                recognized_ids.append(student.student_id)
                match_results[i] = FaceMatchResult(
                    box=box,
                    detection_confidence=det_conf,
                    is_recognized=True,
                    status="RECOGNIZED",
                    student_id=student.student_id,
                    student_name=student.full_name,
                    roll_number=student.roll_number,
                    similarity=sim,
                    distance=dist,
                    threshold_applied=effective_threshold,
                    landmarks=landmarks,
                )
            else:
                # Below threshold or duplicate match: flag as UNKNOWN or LOW_CONFIDENCE
                status_label = "LOW_CONFIDENCE" if (student is not None and sim > 0.30 and sim < effective_threshold) else "UNKNOWN"
                match_results[i] = FaceMatchResult(
                    box=box,
                    detection_confidence=det_conf,
                    is_recognized=False,
                    status=status_label,
                    student_id=None,
                    student_name=None,
                    roll_number=None,
                    similarity=sim if sim > 0 else 0.0,
                    distance=dist,
                    threshold_applied=effective_threshold,
                    landmarks=landmarks,
                )

        recognized_count = len(recognized_ids)
        unknown_count = total_detected - recognized_count

        logger.info(
            f"Recognition completed: {recognized_count} recognized, {unknown_count} unknown "
            f"(threshold={effective_threshold}, min_confidence={effective_min_conf})"
        )

        return RecognitionSummary(
            class_id=class_id,
            total_faces_detected=total_detected,
            recognized_count=recognized_count,
            unknown_count=unknown_count,
            threshold=effective_threshold,
            matches=[m for m in match_results if m is not None],
            recognized_student_ids=recognized_ids,
        )

    def recognize_class_attendance(
        self,
        db: Session,
        class_id: int,
        image_data: Union[bytes, np.ndarray],
        threshold: Optional[float] = None,
        min_confidence: Optional[float] = None,
    ) -> RecognitionSummary:
        """
        High-level orchestrator:
        1. Loads enrolled student vectors strictly for class_id.
        2. Detects and compares all faces in classroom image.
        3. Returns structured recognition summary.
        """
        roster = self.load_enrolled_students_for_class(db, class_id)
        return self.recognize_faces_in_image(
            image_data=image_data,
            enrolled_roster=roster,
            threshold=threshold,
            min_confidence=min_confidence,
            class_id=class_id,
        )

    def annotate_image(
        self,
        image_data: Union[bytes, np.ndarray],
        matches: List[FaceMatchResult],
    ) -> bytes:
        """
        Draws bounding boxes and labels (recognized names and confidence scores)
        on the classroom photograph.
        Green boxes + names for recognized students.
        Red/Amber boxes + 'Unknown' for unrecognized/low-confidence faces.
        """
        if isinstance(image_data, bytes):
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_data, np.ndarray):
            img = image_data.copy()
        else:
            raise ValueError("image_data must be bytes or numpy array.")

        if img is None:
            return image_data if isinstance(image_data, bytes) else b""

        h, w = img.shape[:2]
        base_dim = max(h, w)
        thickness = max(1, int(round(base_dim / 650.0)))
        font_scale = max(0.42, base_dim / 1400.0)

        for match in matches:
            if not match.box or len(match.box) != 4:
                continue
            x, y, bw, bh = match.box
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            bw = max(1, min(bw, w - x))
            bh = max(1, min(bh, h - y))

            if match.is_recognized:
                # Vibrant Green in BGR
                color = (34, 197, 94)
                conf_pct = int(round(match.similarity * 100))
                name = match.student_name or f"Student #{match.student_id}"
                label = f"{name} ({conf_pct}%)"
            else:
                # Coral Red / Amber in BGR
                color = (68, 68, 239) if match.status == "UNKNOWN" else (30, 140, 245)
                conf_pct = int(round(match.similarity * 100))
                label = "Unknown Face" if match.status == "UNKNOWN" else f"Low Confidence ({conf_pct}%)"

            # Draw bounding box
            cv2.rectangle(img, (x, y), (x + bw, y + bh), color, thickness * 2)

            # Draw filled badge for text label
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )
            pad = 6
            badge_h = text_h + pad * 2
            badge_w = text_w + pad * 2

            # Try placing above box; if not enough room, place inside box
            if y - badge_h >= 0:
                y1 = y - badge_h
                y2 = y
            else:
                y1 = y
                y2 = y + badge_h

            x1 = x
            x2 = min(w, x + badge_w)

            cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
            cv2.putText(
                img,
                label,
                (x1 + pad, y2 - pad),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

        success, encoded = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if success:
            return encoded.tobytes()
        return image_data if isinstance(image_data, bytes) else b""


face_recognition_service = FaceRecognitionService()

