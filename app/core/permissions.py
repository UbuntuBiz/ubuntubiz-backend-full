from enum import Enum
from typing import List
from fastapi import HTTPException, status
from app.core.tenant import get_current_user_role


class Role(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    CASHIER = "cashier"


def require_roles(allowed_roles: List[Role]):
    """
    Dependency or validator to ensure current user has one of the required roles.
    """
    def role_checker():
        current_role = get_current_user_role()
        if not current_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials not found or invalid"
            )
        if current_role not in [r.value for r in allowed_roles] and current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_role}'"
            )
        return current_role
    return role_checker
