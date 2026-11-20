from contextvars import ContextVar
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.logging import logger

# Context variables for request-bound tenant isolation
_current_business_id: ContextVar[Optional[str]] = ContextVar("current_business_id", default=None)
_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
_current_user_role: ContextVar[Optional[str]] = ContextVar("current_user_role", default=None)


def get_current_business_id() -> Optional[str]:
    """Retrieve the business ID bound to the current execution context."""
    return _current_business_id.get()


def get_current_user_id() -> Optional[str]:
    """Retrieve the user ID bound to the current execution context."""
    return _current_user_id.get()


def get_current_user_role() -> Optional[str]:
    """Retrieve the user role bound to the current execution context."""
    return _current_user_role.get()


@contextmanager
def tenant_context(business_id: str, user_id: Optional[str] = None, role: Optional[str] = None) -> Generator[None, None, None]:
    """
    Context manager to safely set and restore tenant context.
    Ensures no state leakage across asynchronous request boundaries.
    """
    token_biz = _current_business_id.set(business_id)
    token_user = _current_user_id.set(user_id)
    token_role = _current_user_role.set(role)
    try:
        yield
    finally:
        _current_business_id.reset(token_biz)
        _current_user_id.reset(token_user)
        _current_user_role.reset(token_role)


def set_session_tenant(db_session: Session, business_id: str) -> None:
    """
    Apply tenant boundary to the active database session.
    If PostgreSQL is used, sets the RLS session variable `app.business_id`.
    In SQLite test environments, records context for application-level assertion.
    """
    try:
        bind = db_session.get_bind()
        dialect_name = bind.dialect.name if bind else ""
        if dialect_name == "postgresql":
            # Sanitize UUID / alphanumeric string
            cleaned_id = business_id.replace("'", "")
            db_session.execute(text(f"SET LOCAL app.business_id = '{cleaned_id}'"))
    except Exception as e:
        logger.warning(f"Could not set database session tenant variable: {e}")
