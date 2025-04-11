import uuid
from datetime import date
from typing import Any, List

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AvailabilityCreate, AvailabilityPublic,
    AvailabilityUpdate, Message, UserType
)

router = APIRouter(tags=["availability"])


@router.post("/", response_model=AvailabilityPublic)
def create_availability(
        availability_in: AvailabilityCreate,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Create a new availability slot (nutritionist only).
    """
    if current_user.user_type != UserType.NUTRITIONIST:
        raise HTTPException(
            status_code=403,
            detail="Only nutritionists can create availability slots"
        )

    # Validate time range
    if availability_in.start_time >= availability_in.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    # For recurring slots, day_of_week is required
    if availability_in.is_recurring and availability_in.day_of_week is None:
        raise HTTPException(
            status_code=400,
            detail="Day of week is required for recurring availability"
        )

    # For non-recurring slots, specific_date is required
    if not availability_in.is_recurring and availability_in.specific_date is None:
        raise HTTPException(
            status_code=400,
            detail="Specific date is required for non-recurring availability"
        )

    availability = crud.create_availability(
        session=session,
        availability_in=availability_in,
        nutritionist_id=current_user.id
    )

    return availability


@router.get("/", response_model=List[AvailabilityPublic])
def read_availabilities(
        nutritionist_id: uuid.UUID,
        session: SessionDep,
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    Get availability slots for a nutritionist.
    """
    # Check if the nutritionist exists and is a nutritionist
    user = crud.get_user_by_id(session=session, user_id=nutritionist_id)
    if not user or user.user_type != UserType.NUTRITIONIST:
        raise HTTPException(
            status_code=404,
            detail="Nutritionist not found"
        )

    availabilities = crud.get_availabilities_by_nutritionist(
        session=session,
        nutritionist_id=nutritionist_id,
        skip=skip,
        limit=limit
    )

    return availabilities


@router.get("/date-range", response_model=List[AvailabilityPublic])
def read_availabilities_by_date_range(
        nutritionist_id: uuid.UUID,
        start_date: date,
        end_date: date,
        session: SessionDep,
) -> Any:
    """
    Get availability slots for a nutritionist within a date range.
    """
    # Check date range
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )

    # Check if the nutritionist exists and is a nutritionist
    user = crud.get_user_by_id(session=session, user_id=nutritionist_id)
    if not user or user.user_type != UserType.NUTRITIONIST:
        raise HTTPException(
            status_code=404,
            detail="Nutritionist not found"
        )

    availabilities = crud.get_availabilities_by_date_range(
        session=session,
        nutritionist_id=nutritionist_id,
        start_date=start_date,
        end_date=end_date
    )

    return availabilities


@router.get("/{availability_id}", response_model=AvailabilityPublic)
def read_availability(
        availability_id: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Get a specific availability slot.
    """
    availability = crud.get_availability_by_id(session=session, availability_id=availability_id)

    if not availability:
        raise HTTPException(
            status_code=404,
            detail="Availability slot not found"
        )

    # Verify that the current user is either the nutritionist who owns this slot or an admin
    if (availability.nutritionist_id != current_user.id and
            current_user.user_type != UserType.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    return availability


@router.patch("/{availability_id}", response_model=AvailabilityPublic)
def update_availability(
        availability_id: uuid.UUID,
        availability_in: AvailabilityUpdate,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Update an availability slot (nutritionist only).
    """
    availability = crud.get_availability_by_id(session=session, availability_id=availability_id)

    if not availability:
        raise HTTPException(
            status_code=404,
            detail="Availability slot not found"
        )

    # Verify that the current user is the nutritionist who owns this slot
    if availability.nutritionist_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # Validate start/end time if provided
    start_time = availability_in.start_time or availability.start_time
    end_time = availability_in.end_time or availability.end_time
    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    updated_availability = crud.update_availability(
        session=session,
        db_availability=availability,
        availability_in=availability_in
    )

    return updated_availability


@router.delete("/{availability_id}", response_model=Message)
def delete_availability(
        availability_id: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Delete an availability slot (nutritionist only).
    """
    availability = crud.get_availability_by_id(session=session, availability_id=availability_id)

    if not availability:
        raise HTTPException(
            status_code=404,
            detail="Availability slot not found"
        )

    # Verify that the current user is the nutritionist who owns this slot
    if availability.nutritionist_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    crud.delete_availability(session=session, availability_id=availability_id)

    return Message(message="Availability slot deleted successfully")