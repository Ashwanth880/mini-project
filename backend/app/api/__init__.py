from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.classes import router as classes_router
from app.api.subjects import router as subjects_router
from app.api.teachers import router as teachers_router
from app.api.assignments import router as assignments_router
from app.api.students import router as students_router
from app.api.attendance import router as attendance_router
from app.api.teacher_portal import router as teacher_portal_router
from app.api.student_portal import router as student_portal_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(classes_router)
api_router.include_router(subjects_router)
api_router.include_router(teachers_router)
api_router.include_router(assignments_router)
api_router.include_router(students_router)
api_router.include_router(attendance_router)
api_router.include_router(teacher_portal_router)
api_router.include_router(student_portal_router)

__all__ = ["api_router"]
