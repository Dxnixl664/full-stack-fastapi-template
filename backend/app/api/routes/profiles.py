import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import ProfileCreate, ProfilePublic, ProfileUpdate

router = APIRouter(tags=["profiles"])


@router.get("/me", response_model=ProfilePublic)
def read_profile_me(
        current_user: CurrentUser, session: SessionDep
) -> Any:
    """
    Get current user's profile.
    """
    profile = crud.get_profile_by_user_id(session=session, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/me", response_model=ProfilePublic)
def create_profile_me(
        profile_in: ProfileCreate, current_user: CurrentUser, session: SessionDep
) -> Any:
    """
    Create profile for current user.
    """
    # Check if profile already exists
    existing_profile = crud.get_profile_by_user_id(session=session, user_id=current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Profile already exists for this user",
        )

    profile = crud.create_profile(
        session=session, profile_in=profile_in, user_id=current_user.id
    )
    return profile


@router.patch("/me", response_model=ProfilePublic)
def update_profile_me(
        profile_in: ProfileUpdate, current_user: CurrentUser, session: SessionDep
) -> Any:
    """
    Update current user's profile.
    """
    profile = crud.get_profile_by_user_id(session=session, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    updated_profile = crud.update_profile(
        session=session, db_profile=profile, profile_in=profile_in
    )
    return updated_profile


@router.get("/{user_id}", response_model=ProfilePublic)
def read_profile(
        user_id: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep
) -> Any:
    """
    Get profile by user ID.
    """
    # Allow users to view their own profile or if they're a nutritionist/admin
    if user_id != current_user.id and current_user.user_type == UserType.CLIENT:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to access this profile"
        )

    profile = crud.get_profile_by_user_id(session=session, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile