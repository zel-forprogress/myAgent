import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
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
        created_at=user.created_at.isoformat(),
    )


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = 1,
    page_size: int = 15,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserListResponse:
    total = db.query(User).count()
    offset = (max(page, 1) - 1) * max(page_size, 1)
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return UserListResponse(
        users=[serialize_user_item(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    request: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    db.delete(user)
    db.commit()
    return {"detail": "User deleted successfully"}
