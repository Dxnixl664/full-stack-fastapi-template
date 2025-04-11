import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import UserPublic, UserType, UsersPublic

router = APIRouter(tags=["nutritionists"])


@router.get("/", response_model=UsersPublic)
def read_nutritionists(
        session: SessionDep,
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    Retrieve all nutritionists.
    """
    nutritionists = crud.get_users(
        session=session,
        skip=skip,
        limit=limit,
        user_type=UserType.NUTRITIONIST
    )
    count = crud.get_users_count(
        session=session,
        user_type=UserType.NUTRITIONIST
    )
    return UsersPublic(data=nutritionists, count=count)


@router.get("/{nutritionist_id}", response_model=UserPublic)
def read_nutritionist(
        nutritionist_id: uuid.UUID,
        session: SessionDep,
) -> Any:
    """
    Get a specific nutritionist by ID.
    """
    user = crud.get_user_by_id(session=session, user_id=nutritionist_id)

    if not user or user.user_type != UserType.NUTRITIONIST:
        raise HTTPException(
            status_code=404,
            detail="Nutritionist not found"
        )

    return user