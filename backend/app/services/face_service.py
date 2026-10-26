"""
Computer Vision Face Service.
Handles face detection, image quality verification, feature embedding extraction,
and face similarity matching.

Uses OpenCV YuNet for face detection and OpenCV SFace for 128D feature embedding extraction,
with Haar Cascade as a secondary validation fallback.
"""

import io
import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger("one-click-attendance.face_service")


class FaceEnrollmentError(Exception):
    """Base exception for face enrollment pipeline errors."""
    pass


class StudentNotFoundError(FaceEnrollmentError):
    """Raised when the student record cannot be found in the database."""
    pass


class InvalidImageError(FaceEnrollmentError):
    """Raised when the uploaded file cannot be parsed as a valid image."""
    pass


class NoFaceDetectedError(FaceEnrollmentError):
    """Raised when no face is found in the uploaded image."""
    def __init__(self, message: str = "No face detected"):
        super().__init__(message)


class MultipleFacesDetectedError(FaceEnrollmentError):
    """Raised when more than one face is detected in the enrollment image."""
    def __init__(self, message: str = "Multiple faces detected", face_count: int = 0):
        super().__init__(message)
        self.face_count = face_count


class ImageQualityError(FaceEnrollmentError):
    """Raised when the detected face fails image quality standards (blurry, dark, low-res)."""
    pass


class FaceService:
    """
    Service for face detection, image quality validation, and feature embedding extraction.
    """

    YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
    SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"
    HAAR_FILENAME = "haarcascade_frontalface_default.xml"

    YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
    HAAR_URL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

    def __init__(self):
        self.match_threshold = settings.FACE_MATCH_THRESHOLD
        self.min_confidence = settings.MIN_FACE_CONFIDENCE
        self.models_dir = settings.CV_MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._detector: Optional[cv2.FaceDetectorYN] = None
        self._recognizer: Optional[cv2.FaceRecognizerSF] = None
        self._haar_cascade: Optional[cv2.CascadeClassifier] = None

    def _ensure_model_file(self, filename: str, url: str) -> Path:
        """Ensures a model file exists locally; downloads it from remote if necessary."""
        dest_path = self.models_dir / filename
        if not dest_path.exists() or dest_path.stat().st_size < 1000:
            logger.info(f"Downloading required CV model '{filename}' from {url}...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "OneClickAttendance/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as f:
                    f.write(resp.read())
                logger.info(f"Successfully downloaded '{filename}' ({dest_path.stat().st_size} bytes).")
            except Exception as exc:
                logger.error(f"Failed to download model '{filename}': {exc}")
                raise FaceEnrollmentError(f"Face enrollment model '{filename}' is unavailable: {exc}")
        return dest_path

    @property
    def detector(self) -> cv2.FaceDetectorYN:
        """Lazily loads and returns the YuNet face detector."""
        if self._detector is None:
            model_path = self._ensure_model_file(self.YUNET_FILENAME, self.YUNET_URL)
            logger.info(f"Initializing YuNet Face Detector from {model_path}...")
            self._detector = cv2.FaceDetectorYN.create(
                model=str(model_path),
                config="",
                input_size=(320, 320),
                score_threshold=float(self.min_confidence),
                nms_threshold=0.3,
                top_k=5000,
            )
        return self._detector

    @property
    def recognizer(self) -> cv2.FaceRecognizerSF:
        """Lazily loads and returns the SFace feature extractor."""
        if self._recognizer is None:
            model_path = self._ensure_model_file(self.SFACE_FILENAME, self.SFACE_URL)
            logger.info(f"Initializing SFace Feature Recognizer from {model_path}...")
            self._recognizer = cv2.FaceRecognizerSF.create(
                model=str(model_path),
                config="",
            )
        return self._recognizer

    @property
    def haar_cascade(self) -> Optional[Any]:
        """Lazily loads Haar cascade as a fallback validator if supported by OpenCV."""
        if self._haar_cascade is None and hasattr(cv2, "CascadeClassifier"):
            try:
                model_path = self._ensure_model_file(self.HAAR_FILENAME, self.HAAR_URL)
                cascade = cv2.CascadeClassifier(str(model_path))
                if not cascade.empty():
                    self._haar_cascade = cascade
            except Exception as e:
                logger.warning(f"Haar cascade initialization skipped: {e}")
        return self._haar_cascade

    def decode_image_bytes(self, image_bytes: bytes) -> np.ndarray:
        """
        Validates and decodes image bytes into a BGR OpenCV NumPy array.
        Raises InvalidImageError if corrupt or unreadable.
        """
        if not image_bytes or len(image_bytes) == 0:
            raise InvalidImageError("Uploaded image file is empty.")

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img.verify()
        except Exception as exc:
            logger.warning(f"Image raster verification failed: {exc}")
            raise InvalidImageError(f"Corrupted or invalid image file: {str(exc)}")

        nparr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise InvalidImageError("Failed to decode image data into raster array.")

        return img_bgr

    def detect_faces(self, img_bgr: np.ndarray, min_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Detects faces in a BGR image using YuNet.
        Returns a list of face dicts:
            {
                "box": [x, y, w, h],
                "confidence": float,
                "landmarks": [[x, y], ...],
                "raw": np.ndarray (15-element YuNet representation)
            }
        """
        h, w = img_bgr.shape[:2]
        confidence_thresh = min_confidence if min_confidence is not None else self.min_confidence

        detector = self.detector
        detector.setInputSize((w, h))
        detector.setScoreThreshold(confidence_thresh)

        _, raw_faces = detector.detect(img_bgr)
        detected_list = []

        if raw_faces is not None and len(raw_faces) > 0:
            for face in raw_faces:
                score = float(face[14])
                if score >= confidence_thresh:
                    x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                    # Ensure positive dimensions within image boundaries
                    if fw > 10 and fh > 10:
                        landmarks = [[float(face[4 + 2 * j]), float(face[5 + 2 * j])] for j in range(5)]
                        detected_list.append({
                            "box": [x, y, fw, fh],
                            "confidence": round(score, 4),
                            "landmarks": landmarks,
                            "raw": face,
                        })

        # Secondary fallback with Haar cascade if YuNet finds 0 faces but image is large enough
        if len(detected_list) == 0 and self.haar_cascade is not None:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            haar_faces = self.haar_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
            )
            for (hx, hy, hw, hh) in haar_faces:
                # Synthesize standard raw face representation for SFace alignment
                # Landmarks estimated based on standard face geometry proportions
                re_x, re_y = hx + hw * 0.35, hy + hh * 0.38
                le_x, le_y = hx + hw * 0.65, hy + hh * 0.38
                nt_x, nt_y = hx + hw * 0.50, hy + hh * 0.58
                rcm_x, rcm_y = hx + hw * 0.38, hy + hh * 0.78
                lcm_x, lcm_y = hx + hw * 0.62, hy + hh * 0.78
                synthetic_raw = np.array([
                    hx, hy, hw, hh,
                    re_x, re_y, le_x, le_y, nt_x, nt_y, rcm_x, rcm_y, lcm_x, lcm_y,
                    0.80
                ], dtype=np.float32)
                detected_list.append({
                    "box": [int(hx), int(hy), int(hw), int(hh)],
                    "confidence": 0.80,
                    "landmarks": [[re_x, re_y], [le_x, le_y], [nt_x, nt_y], [rcm_x, rcm_y], [lcm_x, lcm_y]],
                    "raw": synthetic_raw,
                })

        logger.info(f"Detected {len(detected_list)} face(s) in image (shape={img_bgr.shape}).")
        return detected_list

    def check_image_quality(
        self,
        img_bgr: np.ndarray,
        face_info: Dict[str, Any],
        min_sharpness: float = 35.0,
        min_brightness: float = 35.0,
        max_brightness: float = 230.0,
        min_face_size: int = 50,
    ) -> Tuple[bool, str, Dict[str, float]]:
        """
        Performs basic quality checks on the detected face and image:
        1. Sharpness / Blur detection using Laplacian variance.
        2. Lighting / Exposure checks (mean pixel brightness).
        3. Face resolution / bounding box size checks.

        Returns:
            Tuple[is_acceptable (bool), failure_reason (str), metrics (dict)]
        """
        h, w = img_bgr.shape[:2]
        x, y, fw, fh = face_info["box"]

        # Clamp face crop to valid image bounds
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + fw)
        y2 = min(h, y + fh)

        if x2 - x1 < 10 or y2 - y1 < 10:
            return False, "Face bounding box out of image bounds.", {}

        face_crop = img_bgr[y1:y2, x1:x2]
        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

        # 1. Sharpness calculation (Laplacian variance on face region)
        sharpness_face = float(cv2.Laplacian(gray_face, cv2.CV_64F).var())
        effective_sharpness = sharpness_face

        # 2. Lighting / Exposure calculation
        brightness = float(gray_face.mean())

        metrics = {
            "sharpness": round(effective_sharpness, 2),
            "brightness": round(brightness, 2),
            "face_width": fw,
            "face_height": fh,
            "image_width": w,
            "image_height": h,
        }

        # Check face resolution
        if fw < min_face_size or fh < min_face_size:
            reason = (
                f"Image quality insufficient: Face resolution is too small ({fw}x{fh} px). "
                f"Minimum {min_face_size}x{min_face_size} px required."
            )
            logger.warning(reason)
            return False, reason, metrics

        # Check underexposure (too dark)
        if brightness < min_brightness:
            reason = (
                f"Image quality insufficient: Image is too dark "
                f"(average brightness {brightness:.1f} < threshold {min_brightness}). "
                f"Please upload a well-lit photo."
            )
            logger.warning(reason)
            return False, reason, metrics

        # Check overexposure (too bright / washed out)
        if brightness > max_brightness:
            reason = (
                f"Image quality insufficient: Image is overexposed "
                f"(average brightness {brightness:.1f} > threshold {max_brightness}). "
                f"Please avoid direct glare or overexposed lighting."
            )
            logger.warning(reason)
            return False, reason, metrics

        # Check blur
        if effective_sharpness < min_sharpness:
            reason = (
                f"Image quality insufficient: Image is too blurry "
                f"(sharpness score {effective_sharpness:.1f} < threshold {min_sharpness}). "
                f"Please upload a clearer, sharper photo."
            )
            logger.warning(reason)
            return False, reason, metrics

        logger.info(f"Image quality checks passed: {metrics}")
        return True, "", metrics

    def extract_face_embedding(self, img_bgr: np.ndarray, face_info: Dict[str, Any]) -> np.ndarray:
        """
        Aligns the face crop and generates a 128D normalized feature embedding using SFace.
        Returns a 1D float32 NumPy array of length 128 with L2 norm == 1.0.
        """
        raw_face = face_info["raw"]
        recognizer = self.recognizer

        # Align and crop face to standard 112x112 portrait using the 5 landmarks
        aligned_face = recognizer.alignCrop(img_bgr, raw_face)

        # Extract 128D feature embedding
        feature_raw = recognizer.feature(aligned_face)
        embedding = feature_raw.flatten().astype(np.float32)

        # L2 Normalization
        norm = np.linalg.norm(embedding)
        if norm > 1e-6:
            embedding = embedding / norm
        else:
            raise FaceEnrollmentError("Face enrollment failed: generated embedding norm is zero.")

        if len(embedding) != 128:
            raise FaceEnrollmentError(f"Face enrollment failed: expected 128D vector, got {len(embedding)}D.")

        return embedding

    @staticmethod
    def serialize_embedding(embedding: np.ndarray) -> str:
        """Serializes numpy embedding vector into a compact JSON string for database storage."""
        return json.dumps([round(float(v), 6) for v in embedding.tolist()])

    @staticmethod
    def deserialize_embedding(embedding_json: str) -> np.ndarray:
        """Deserializes JSON string back into a numpy float32 vector."""
        if not embedding_json or embedding_json.strip() == "":
            return np.array([], dtype=np.float32)
        return np.array(json.loads(embedding_json), dtype=np.float32)

    def compute_similarity(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        """
        Computes cosine similarity between two 128D normalized face embedding vectors.
        Returns float between -1.0 and 1.0 (typically 0.0 to 1.0 for normalized face embeddings).
        """
        if embedding_a is None or embedding_b is None or len(embedding_a) == 0 or len(embedding_b) == 0:
            return 0.0
        norm_a = np.linalg.norm(embedding_a)
        norm_b = np.linalg.norm(embedding_b)
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return float(np.dot(embedding_a, embedding_b) / (norm_a * norm_b))

    def process_face_enrollment(
        self,
        image_bytes: bytes,
    ) -> Tuple[np.ndarray, Dict[str, Any], Dict[str, float]]:
        """
        Complete face enrollment processing pipeline:
        1. Decode and validate raster image.
        2. Detect faces.
        3. Require exactly one usable face (reject 0 faces, reject >1 faces).
        4. Perform basic image quality checks.
        5. Generate 128D face embedding using SFace.

        Returns:
            Tuple[embedding_vector, detected_face_info, quality_metrics]

        Raises:
            InvalidImageError
            NoFaceDetectedError
            MultipleFacesDetectedError
            ImageQualityError
            FaceEnrollmentError
        """
        # Step 1: Decode image
        img_bgr = self.decode_image_bytes(image_bytes)

        # Step 2: Detect faces
        faces = self.detect_faces(img_bgr)
        face_count = len(faces)

        # Step 3: Require exactly one face
        if face_count == 0:
            logger.warning("Enrollment rejected: No face detected in uploaded image.")
            raise NoFaceDetectedError("No face detected")

        if face_count > 1:
            logger.warning(f"Enrollment rejected: Multiple faces detected ({face_count} faces found).")
            raise MultipleFacesDetectedError(
                f"Multiple faces detected: Found {face_count} faces in image. "
                "Please upload a portrait containing only one student.",
                face_count=face_count,
            )

        target_face = faces[0]

        # Step 4: Perform basic quality checks
        is_quality_ok, reason, metrics = self.check_image_quality(img_bgr, target_face)
        if not is_quality_ok:
            raise ImageQualityError(reason)

        # Step 5: Generate face embedding
        try:
            embedding = self.extract_face_embedding(img_bgr, target_face)
        except Exception as exc:
            logger.error(f"Failed to extract face embedding: {exc}")
            raise FaceEnrollmentError(f"Face enrollment failed: could not generate embedding ({str(exc)})")

        logger.info(
            f"Face enrollment processing succeeded! Embedding extracted with confidence={target_face['confidence']}"
        )
        return embedding, target_face, metrics

    def enroll_student_face(
        self,
        db: Any,
        student_id: int,
        image_bytes: bytes,
        filename: str = "portrait.jpg",
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end student face enrollment:
        1. Validate student exists in the database.
        2. Validate image format, size, and raster integrity.
        3. Detect faces (require exactly one face; reject 0 faces, reject >1 faces).
        4. Perform basic image quality checks (sharpness, lighting, resolution).
        5. Extract 128D SFace feature embedding vector.
        6. Store original image securely in settings.FACES_DIR with non-predictable UUID filename.
        7. Store embedding associated strictly with student in student_faces table.
        8. Atomically update student.face_enrolled = True.

        Ensures the system NEVER associates an embedding with the wrong student.
        """
        import uuid
        from datetime import datetime, timezone
        from app.models.student import Student, StudentFace

        logger.info(f"Initiating face enrollment for student_id={student_id}, filename='{filename}'")

        # 1. Verify student exists
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            logger.warning(f"Student ID {student_id} not found in database.")
            raise StudentNotFoundError(f"Student not found with ID {student_id}")

        # 2. Image validation (format, size)
        MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
        ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
        ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}

        if not image_bytes or len(image_bytes) == 0:
            raise InvalidImageError("Uploaded image file is empty.")

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise InvalidImageError(f"File size exceeds maximum allowed limit of {MAX_IMAGE_SIZE // (1024 * 1024)}MB.")

        ext = Path(filename).suffix.lower() if filename else ".jpg"
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise InvalidImageError(f"Unsupported file extension '{ext}'. Allowed extensions are: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_format = pil_img.format.upper() if pil_img.format else ""
            if pil_format not in ALLOWED_PIL_FORMATS:
                raise InvalidImageError(f"Image format '{pil_format}' is not permitted. Only JPEG, PNG, or WebP allowed.")
            width, height = pil_img.size
            if width < 32 or height < 32:
                raise InvalidImageError("Image resolution is too small (minimum 32x32 pixels required).")
            if width > 6000 or height > 6000:
                raise InvalidImageError("Image dimensions exceed maximum allowed dimensions (6000x6000px).")
        except InvalidImageError:
            raise
        except Exception as exc:
            raise InvalidImageError(f"Corrupted or invalid image file: {str(exc)}")

        # 3, 4, 5. Process face enrollment (detect faces, 1-face check, quality checks, 128D embedding)
        embedding, target_face, metrics = self.process_face_enrollment(image_bytes)

        # 6. Secure file storage with sanitized, unique, unguessable filename
        settings.FACES_DIR.mkdir(parents=True, exist_ok=True)
        canonical_ext = ".jpg" if pil_format == "JPEG" else f".{pil_format.lower()}"
        secure_filename = f"student_{student.id}_{uuid.uuid4().hex[:12]}{canonical_ext}"
        destination_path = settings.FACES_DIR / secure_filename
        relative_url = f"/faces/{secure_filename}"

        try:
            destination_path.write_bytes(image_bytes)
            logger.info(f"Stored student face image securely at {destination_path}")
        except Exception as exc:
            logger.error(f"Failed to write image file: {exc}")
            raise FaceEnrollmentError(f"Face enrollment failed: could not save image to disk ({str(exc)})")

        # 7 & 8. Atomically store embedding and update student status in database
        try:
            # Query existing faces for this student
            existing_face = db.query(StudentFace).filter(
                StudentFace.student_id == student.id,
                StudentFace.is_primary == True
            ).first()

            serialized_vector = self.serialize_embedding(embedding)

            if existing_face:
                existing_face.embedding = serialized_vector
                existing_face.image_path = relative_url
                existing_face.created_at = datetime.now(timezone.utc)
            else:
                new_face = StudentFace(
                    student_id=student.id,
                    embedding=serialized_vector,
                    image_path=relative_url,
                    is_primary=True,
                )
                db.add(new_face)

            student.face_enrolled = True
            db.commit()
            db.refresh(student)
            logger.info(
                f"Student ID {student.id} ('{student.full_name}', roll={student.roll_number}) face successfully enrolled and committed."
            )
        except Exception as exc:
            db.rollback()
            if destination_path.exists():
                destination_path.unlink(missing_ok=True)
            logger.error(f"Database transaction error during enrollment for student {student.id}: {exc}")
            raise FaceEnrollmentError(f"Face enrollment failed: database transaction error ({str(exc)})")

        return {
            "success": True,
            "message": "Face enrolled successfully",
            "detail": "Face enrolled successfully",
            "student_id": student.id,
            "roll_number": student.roll_number,
            "full_name": student.full_name,
            "face_enrolled": True,
            "face_image_path": relative_url,
            "embedding_dimension": len(embedding),
            "face_confidence": target_face["confidence"],
            "quality_metrics": metrics,
        }


face_service = FaceService()
