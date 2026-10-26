import html
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, LoginRequest, TokenResponse
from app.utils.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """
    User registration for faculty and staff setup.
    Hashes passwords using bcrypt before saving.
    Prevents unauthorized self-escalation to ADMIN role.
    """
    if not user_in.password or len(user_in.password.strip()) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    if len(user_in.password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot exceed 128 characters.",
        )

    # Prevent unauthenticated privilege escalation:
    # If the system already has registered users, unauthenticated self-registration as ADMIN is forbidden.
    if user_in.role == UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        if admin_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration as administrator is restricted. Contact an existing system administrator.",
            )

    existing_user = db.query(User).filter(
        or_(User.username == user_in.username, User.email == user_in.email)
    ).first()
    if existing_user:
        if existing_user.username == user_in.username:
            detail = "A user with this username already exists."
        else:
            detail = "A user with this email already exists."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # Hash password with bcrypt - Never store plain text
    hashed_pwd = hash_password(user_in.password)

    new_user = User(
        username=html.escape(user_in.username.strip()),
        email=user_in.email.strip().lower(),
        hashed_password=hashed_pwd,
        full_name=html.escape(user_in.full_name.strip()),
        role=user_in.role,
        department=html.escape(user_in.department.strip()) if user_in.department else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate user with username/email and password.
    Returns a signed JWT bearer token and user role details.
    """
    user = db.query(User).filter(
        or_(
            User.username == login_data.username,
            User.email == login_data.username,
            User.teacher_id == login_data.username,
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact your Class Teacher or Administrator.",
        )

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Safely extract role string whether user.role is Enum or string
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role or "SUBJECT_TEACHER")

    # Create JWT access token
    token_payload = {
        "sub": str(user.id),
        "username": str(user.username),
        "role": role_str,
    }
    access_token = create_access_token(data=token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get profile of the currently authenticated user.
    Requires a valid JWT Bearer token.
    """
    return UserResponse.model_validate(current_user)

