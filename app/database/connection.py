from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings
from app.core.tenant import get_current_business_id, set_session_tenant

settings = get_settings()

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DB_ECHO,
    pool_pre_ping=True if not is_sqlite else False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding an isolated database session.
    Automatically applies tenant context (RLS) if a business is authenticated.
    """
    db: Session = SessionLocal()
    current_biz = get_current_business_id()
    if current_biz:
        set_session_tenant(db, current_biz)
    try:
        yield db
    finally:
        db.close()
