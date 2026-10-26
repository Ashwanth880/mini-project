import io
import os
import uuid
from pathlib import Path
from typing import Tuple
from PIL import Image
from fastapi import UploadFile, HTTPException, status
from app.config import settings

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Megabytes
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_and_save_face_image(upload_file: UploadFile, student_id: int) -> Tuple[str, str]:
    """
    Validates uploaded face photograph:
    - Validates file type (MIME & extension)
    - Validates file size (max 5MB, not empty)
    - Validates raster image integrity using PIL
    - Securely stores image in settings.FACES_DIR with unique filename
    - Prevents directory traversal and malicious payloads

    Returns:
        Tuple[relative_url, absolute_path_str]
        e.g. ('/faces/student_1_abc123.jpg', '/data/faces/student_1_abc123.jpg')
    """
    if not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    # 1. Validate file extension
    ext = Path(upload_file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions are: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Validate MIME type header if provided
    if upload_file.content_type and upload_file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Content-Type '{upload_file.content_type}'. Must be JPEG, PNG, or WebP.",
        )

    # 3. Read content and validate size
    try:
        content = upload_file.file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(exc)}",
        )

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_IMAGE_SIZE // (1024 * 1024)}MB.",
        )

    # 4. Validate image raster integrity using Pillow
    try:
        img_buffer = io.BytesIO(content)
        img = Image.open(img_buffer)
        img_format = img.format.upper() if img.format else ""

        if img_format not in ALLOWED_PIL_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image format '{img_format}' is not permitted. Only JPEG, PNG, or WebP allowed.",
            )

        # Basic dimension sanity check
        width, height = img.size
        if width < 32 or height < 32:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image resolution is too small for facial recognition (minimum 32x32 pixels required).",
            )
        if width > 6000 or height > 6000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image dimensions exceed maximum allowed dimensions (6000x6000px).",
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or invalid image file: {str(exc)}",
        )

    # 5. Secure storage with non-predictable unique filename
    settings.FACES_DIR.mkdir(parents=True, exist_ok=True)
    canonical_ext = ".jpg" if img_format == "JPEG" else f".{img_format.lower()}"
    secure_filename = f"student_{student_id}_{uuid.uuid4().hex[:12]}{canonical_ext}"
    destination_path = settings.FACES_DIR / secure_filename

    try:
        destination_path.write_bytes(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to securely save face image: {str(exc)}",
        )

    relative_url = f"/faces/{secure_filename}"
    return relative_url, str(destination_path)
