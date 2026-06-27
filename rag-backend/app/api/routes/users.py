import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models import User
from app.schemas import (
    AdminUserCreateRequest,
    UserListItem,
    UserListResponse,
    UserResponse,
)
from app.services.auth_service import (
    create_user,
    get_user_by_id,
    get_user_by_username,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
logger = logging.getLogger(__name__)


def serialize_user_item(user: User) -> UserListItem:
    return UserListItem(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.get("", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserListResponse:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(
        users=[serialize_user_item(u) for u in users],
        total=len(users),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    request: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    existing = get_user_by_username(db, request.username.strip())
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = create_user(
        db,
        username=request.username.strip(),
        password=request.password,
        role=request.role,
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    db.delete(user)
    db.commit()
    return {"detail": "User deleted successfully"}
