"""
Demo/verification endpoints for Phase 1.

These exist purely to exercise and verify role-based access control
end-to-end (ADMIN-only vs TENANT-only routes) ahead of any real domain
endpoints being added in later phases. They are not part of the final
product surface and can be removed once Phase 2+ endpoints provide
equivalent, real coverage.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/admin-only")
def admin_only_route(current_user: User = Depends(require_role(UserRole.ADMIN))) -> dict:
    return {"message": f"Hello ADMIN user {current_user.email}", "role": current_user.role.value}


@router.get("/tenant-only")
def tenant_only_route(current_user: User = Depends(require_role(UserRole.TENANT))) -> dict:
    return {
        "message": f"Hello TENANT user {current_user.email}",
        "role": current_user.role.value,
        "tenant_id": current_user.tenant_id,
    }
