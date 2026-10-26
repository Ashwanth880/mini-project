from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings, BASE_DIR

# SQLite specific connect_args to allow multithreaded access in FastAPI
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///./") or database_url == "sqlite:///attendance.db":
    db_file = (BASE_DIR / "attendance.db").resolve()
    database_url = f"sqlite:///{db_file.as_posix()}"

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from sqlalchemy import inspect, text


def upgrade_schema(db_engine) -> None:
    """Safe, non-destructive backward-compatible schema upgrade."""
    inspector = inspect(db_engine)
    existing_tables = inspector.get_table_names()

    # If users table exists, check if new columns exist and add them if missing
    if "users" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("users")]
        with db_engine.connect() as conn:
            if "student_id" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN student_id INTEGER REFERENCES students(id);"))
            if "teacher_id" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN teacher_id VARCHAR(50);"))
            if "is_active" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1;"))
            conn.commit()


def init_db() -> None:
    """Initialize database tables and run safe non-destructive migrations."""
    # Ensure all models are imported before calling create_all
    import app.models  # noqa: F401
    upgrade_schema(engine)
    Base.metadata.create_all(bind=engine)

