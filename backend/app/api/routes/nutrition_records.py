import uuid
from datetime import date
from typing import Any, List

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message, NutritionRecordCreate,
    NutritionRecordPublic, NutritionRecordUpdate,
    NutritionRecordsPublic, UserType
)

router = APIRouter(tags=["nutrition-records"])


@router.post("/", response_model=NutritionRecordPublic)
def create_nutrition_record(
        record_in: NutritionRecordCreate,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Create a new nutrition record for a client.
    """
    # Only nutritionists and admins can create records for other clients
    # Clients can only create records for themselves
    if current_user.id != record_in.client_id and current_user.user_type == UserType.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # Check if the client exists
    client = crud.get_user_by_id(session=session, user_id=record_in.client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    # Create the nutrition record
    record = crud.create_nutrition_record(
        session=session,
        record_in=record_in,
        created_by_id=current_user.id
    )

    return record


@router.get("/me", response_model=NutritionRecordsPublic)
def read_my_nutrition_records(
        session: SessionDep,
        current_user: CurrentUser,
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    Get all nutrition records for the current user (client).
    """
    # Only clients can view their own records using this endpoint
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only for clients"
        )

    records = crud.get_nutrition_records_by_client(
        session=session,
        client_id=current_user.id,
        skip=skip,
        limit=limit
    )

    count = crud.get_nutrition_records_count_by_client(
        session=session,
        client_id=current_user.id
    )

    return NutritionRecordsPublic(data=records, count=count)


@router.get("/{client_id}", response_model=NutritionRecordsPublic)
def read_client_nutrition_records(
        client_id: uuid.UUID,
        session: SessionDep,
        current_user: CurrentUser,
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    Get all nutrition records for a specific client (nutritionist/admin only).
    """
    # Check permissions - only nutritionists and admins can view other clients' records
    if current_user.user_type == UserType.CLIENT and current_user.id != client_id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # Check if the client exists
    client = crud.get_user_by_id(session=session, user_id=client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    records = crud.get_nutrition_records_by_client(
        session=session,
        client_id=client_id,
        skip=skip,
        limit=limit
    )

    count = crud.get_nutrition_records_count_by_client(
        session=session,
        client_id=client_id
    )

    return NutritionRecordsPublic(data=records, count=count)


@router.get("/date-range/{client_id}", response_model=List[NutritionRecordPublic])
def read_nutrition_records_by_date_range(
        client_id: uuid.UUID,
        start_date: date,
        end_date: date,
        session: SessionDep,
        current_user: CurrentUser,
) -> Any:
    """
    Get nutrition records for a client within a date range.
    """
    # Check date range
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )

    # Check permissions - only nutritionists, admins, or the client themselves can view records
    if current_user.user_type == UserType.CLIENT and current_user.id != client_id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # Check if the client exists
    client = crud.get_user_by_id(session=session, user_id=client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    records = crud.get_nutrition_records_by_date_range(
        session=session,
        client_id=client_id,
        start_date=start_date,
        end_date=end_date
    )

    return records


@router.get("/record/{record_id}", response_model=NutritionRecordPublic)
def read_nutrition_record(
        record_id: uuid.UUID,
        session: SessionDep,
        current_user: CurrentUser,
) -> Any:
    """
    Get a specific nutrition record.
    """
    record = crud.get_nutrition_record_by_id(session=session, record_id=record_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Nutrition record not found"
        )

    # Check permissions - only nutritionists, admins, or the client themselves can view records
    if (current_user.user_type == UserType.CLIENT and
            current_user.id != record.client_id):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    return record


@router.patch("/record/{record_id}", response_model=NutritionRecordPublic)
def update_nutrition_record(
        record_id: uuid.UUID,
        record_in: NutritionRecordUpdate,
        session: SessionDep,
        current_user: CurrentUser,
) -> Any:
    """
    Update a nutrition record.
    """
    record = crud.get_nutrition_record_by_id(session=session, record_id=record_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Nutrition record not found"
        )

    # Check permissions - only the creator or an admin can update records
    if current_user.id != record.created_by_id and current_user.user_type != UserType.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    updated_record = crud.update_nutrition_record(
        session=session,
        db_record=record,
        record_in=record_in
    )

    return updated_record


@router.delete("/record/{record_id}", response_model=Message)
def delete_nutrition_record(
        record_id: uuid.UUID,
        session: SessionDep,
        current_user: CurrentUser,
) -> Any:
    """
    Delete a nutrition record.
    """
    record = crud.get_nutrition_record_by_id(session=session, record_id=record_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Nutrition record not found"
        )

    # Check permissions - only the creator or an admin can delete records
    if current_user.id != record.created_by_id and current_user.user_type != UserType.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    crud.delete_nutrition_record(session=session, record_id=record_id)

    return Message(message="Nutrition record deleted successfully")