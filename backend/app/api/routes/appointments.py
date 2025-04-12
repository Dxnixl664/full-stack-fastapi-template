import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AppointmentCreate, AppointmentPublic,
    AppointmentStatus, AppointmentUpdate, AppointmentsPublic,
    Message, UserType
)
from app.utils import send_email, generate_appointment_email, generate_appointment_update_email, \
    generate_cancellation_email

router = APIRouter(tags=["appointments"])


@router.post("/", response_model=AppointmentPublic)
def create_appointment(
        appointment_in: AppointmentCreate,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Book a new appointment with a nutritionist.
    """
    # Check if the nutritionist exists and is a nutritionist
    nutritionist = crud.get_user_by_id(
        session=session,
        user_id=appointment_in.nutritionist_id
    )
    if not nutritionist or nutritionist.user_type != UserType.NUTRITIONIST:
        raise HTTPException(
            status_code=404,
            detail="Nutritionist not found"
        )

    # Validate time range
    if appointment_in.start_time >= appointment_in.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    # Check if the appointment time is in the future
    appointment_datetime = datetime.combine(
        appointment_in.date,
        appointment_in.start_time
    )
    if appointment_datetime < datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Appointment time must be in the future"
        )

    # Check if the appointment time is available
    # First, get all appointments for the nutritionist on that day
    day_start = appointment_in.date
    day_end = appointment_in.date
    existing_appointments = crud.get_appointments_by_date_range(
        session=session,
        nutritionist_id=appointment_in.nutritionist_id,
        start_date=day_start,
        end_date=day_end,
        status=AppointmentStatus.SCHEDULED
    )

    # Check for time conflicts
    for existing_appt in existing_appointments:
        if (
                (appointment_in.start_time >= existing_appt.start_time and
                 appointment_in.start_time < existing_appt.end_time) or
                (appointment_in.end_time > existing_appt.start_time and
                 appointment_in.end_time <= existing_appt.end_time) or
                (appointment_in.start_time <= existing_appt.start_time and
                 appointment_in.end_time >= existing_appt.end_time)
        ):
            raise HTTPException(
                status_code=400,
                detail="The selected time slot is already booked"
            )

    # Check if the time slot is within the nutritionist's availability
    weekday = appointment_in.date.weekday()
    availabilities = crud.get_availabilities_by_date_range(
        session=session,
        nutritionist_id=appointment_in.nutritionist_id,
        start_date=day_start,
        end_date=day_end
    )

    # Check if the appointment time falls within any of the nutritionist's available slots
    is_available = False
    for avail in availabilities:
        if (avail.is_recurring and avail.day_of_week == weekday) or (
                not avail.is_recurring and avail.specific_date == appointment_in.date
        ):
            if (
                    appointment_in.start_time >= avail.start_time and
                    appointment_in.end_time <= avail.end_time
            ):
                is_available = True
                break

    if not is_available:
        raise HTTPException(
            status_code=400,
            detail="The selected time slot is not available"
        )

    # Create the appointment
    appointment = crud.create_appointment(
        session=session,
        appointment_in=appointment_in,
        client_id=current_user.id
    )

    # Send confirmation emails to both client and nutritionist
    try:
        # Send to client
        client_email_data = generate_appointment_email(
            is_client=True,
            appointment=appointment,
            nutritionist_name=nutritionist.full_name or nutritionist.email
        )
        send_email(
            email_to=current_user.email,
            subject=client_email_data.subject,
            html_content=client_email_data.html_content
        )

        # Send to nutritionist
        nutritionist_email_data = generate_appointment_email(
            is_client=False,
            appointment=appointment,
            client_name=current_user.full_name or current_user.email
        )
        send_email(
            email_to=nutritionist.email,
            subject=nutritionist_email_data.subject,
            html_content=nutritionist_email_data.html_content
        )
    except Exception:
        # If email sending fails, continue anyway
        pass

    return appointment


@router.get("/", response_model=AppointmentsPublic)
def read_appointments(
        session: SessionDep,
        current_user: CurrentUser,
        skip: int = 0,
        limit: int = 100,
        status: Optional[AppointmentStatus] = None,
) -> Any:
    """
    Get all appointments for the current user.
    """
    if current_user.user_type == UserType.NUTRITIONIST:
        # Get appointments as nutritionist
        appointments = crud.get_appointments_by_nutritionist(
            session=session,
            nutritionist_id=current_user.id,
            skip=skip,
            limit=limit
        )
        count = crud.get_appointments_count_by_nutritionist(
            session=session,
            nutritionist_id=current_user.id
        )
    else:
        # Get appointments as client
        appointments = crud.get_appointments_by_client(
            session=session,
            client_id=current_user.id,
            skip=skip,
            limit=limit
        )
        count = crud.get_appointments_count_by_client(
            session=session,
            client_id=current_user.id
        )

    # Filter by status if specified
    if status:
        appointments = [a for a in appointments if a.status == status]
        count = len(appointments)

    return AppointmentsPublic(data=appointments, count=count)


@router.get("/date-range", response_model=List[AppointmentPublic])
def read_appointments_by_date_range(
        start_date: date,
        end_date: date,
        session: SessionDep,
        current_user: CurrentUser,
        status: Optional[AppointmentStatus] = None,
) -> Any:
    """
    Get appointments within a date range.
    """
    # Check date range
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )

    # Get appointments based on user type
    if current_user.user_type == UserType.NUTRITIONIST:
        appointments = crud.get_appointments_by_date_range(
            session=session,
            nutritionist_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            status=status
        )
    else:
        appointments = crud.get_appointments_by_date_range(
            session=session,
            client_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            status=status
        )

    return appointments


@router.get("/{appointment_id}", response_model=AppointmentPublic)
def read_appointment(
        appointment_id: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Get a specific appointment.
    """
    appointment = crud.get_appointment_by_id(session=session, appointment_id=appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # Check if the current user is part of this appointment
    if (current_user.id != appointment.client_id and
            current_user.id != appointment.nutritionist_id and
            current_user.user_type != UserType.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentPublic)
def update_appointment(
        appointment_id: uuid.UUID,
        appointment_in: AppointmentUpdate,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Update an appointment.
    """
    appointment = crud.get_appointment_by_id(session=session, appointment_id=appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # Check if the current user is part of this appointment
    if (current_user.id != appointment.client_id and
            current_user.id != appointment.nutritionist_id and
            current_user.user_type != UserType.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # If changing the date or time, validate the new time slot
    if appointment_in.date or appointment_in.start_time or appointment_in.end_time:
        new_date = appointment_in.date or appointment.date
        new_start_time = appointment_in.start_time or appointment.start_time
        new_end_time = appointment_in.end_time or appointment.end_time

        # Validate time range
        if new_start_time >= new_end_time:
            raise HTTPException(
                status_code=400,
                detail="End time must be after start time"
            )

        # Check if the appointment time is in the future
        new_datetime = datetime.combine(new_date, new_start_time)
        if new_datetime < datetime.now():
            raise HTTPException(
                status_code=400,
                detail="Appointment time must be in the future"
            )

        # Check for conflicts with other appointments
        day_start = new_date
        day_end = new_date
        existing_appointments = crud.get_appointments_by_date_range(
            session=session,
            nutritionist_id=appointment.nutritionist_id,
            start_date=day_start,
            end_date=day_end,
            status=AppointmentStatus.SCHEDULED
        )

        # Check for time conflicts, excluding the current appointment
        for existing_appt in existing_appointments:
            if existing_appt.id != appointment.id and (
                    (new_start_time >= existing_appt.start_time and
                     new_start_time < existing_appt.end_time) or
                    (new_end_time > existing_appt.start_time and
                     new_end_time <= existing_appt.end_time) or
                    (new_start_time <= existing_appt.start_time and
                     new_end_time >= existing_appt.end_time)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="The selected time slot conflicts with another appointment"
                )

        # Check if within nutritionist's availability
        weekday = new_date.weekday()
        availabilities = crud.get_availabilities_by_date_range(
            session=session,
            nutritionist_id=appointment.nutritionist_id,
            start_date=day_start,
            end_date=day_end
        )

        is_available = False
        for avail in availabilities:
            if (avail.is_recurring and avail.day_of_week == weekday) or (
                    not avail.is_recurring and avail.specific_date == new_date
            ):
                if (
                        new_start_time >= avail.start_time and
                        new_end_time <= avail.end_time
                ):
                    is_available = True
                    break

        if not is_available:
            raise HTTPException(
                status_code=400,
                detail="The selected time slot is not within nutritionist's availability"
            )

    # Update the appointment
    updated_appointment = crud.update_appointment(
        session=session,
        db_appointment=appointment,
        appointment_in=appointment_in
    )

    # Send notification emails about the update
    try:
        # Get client and nutritionist info
        client = crud.get_user_by_id(session=session, user_id=appointment.client_id)
        nutritionist = crud.get_user_by_id(session=session, user_id=appointment.nutritionist_id)

        # Notify both parties about the update
        if client and nutritionist:
            # Send to client
            client_email_data = generate_appointment_update_email(
                is_client=True,
                appointment=updated_appointment,
                nutritionist_name=nutritionist.full_name or nutritionist.email
            )
            send_email(
                email_to=client.email,
                subject=client_email_data.subject,
                html_content=client_email_data.html_content
            )

            # Send to nutritionist
            nutritionist_email_data = generate_appointment_update_email(
                is_client=False,
                appointment=updated_appointment,
                client_name=client.full_name or client.email
            )
            send_email(
                email_to=nutritionist.email,
                subject=nutritionist_email_data.subject,
                html_content=nutritionist_email_data.html_content
            )
    except Exception:
        # If email sending fails, continue anyway
        pass

    return updated_appointment


@router.delete("/{appointment_id}", response_model=Message)
def cancel_appointment(
        appointment_id: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep,
) -> Any:
    """
    Cancel an appointment.
    """
    appointment = crud.get_appointment_by_id(session=session, appointment_id=appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # Check if the current user is part of this appointment
    if (current_user.id != appointment.client_id and
            current_user.id != appointment.nutritionist_id and
            current_user.user_type != UserType.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    # Check if the appointment is already cancelled
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Appointment is already cancelled"
        )

    # Cancel the appointment
    cancelled_appointment = crud.cancel_appointment(
        session=session,
        appointment_id=appointment_id
    )

    # Send cancellation notifications
    try:
        # Get client and nutritionist info
        client = crud.get_user_by_id(session=session, user_id=appointment.client_id)
        nutritionist = crud.get_user_by_id(session=session, user_id=appointment.nutritionist_id)

        # Determine who cancelled
        canceller_is_client = current_user.id == appointment.client_id

        # Notify both parties about the cancellation
        if client and nutritionist:
            # Send to client
            client_email_data = generate_cancellation_email(
                is_client=True,
                appointment=appointment,
                nutritionist_name=nutritionist.full_name or nutritionist.email,
                cancelled_by_client=canceller_is_client
            )
            send_email(
                email_to=client.email,
                subject=client_email_data.subject,
                html_content=client_email_data.html_content
            )

            # Send to nutritionist
            nutritionist_email_data = generate_cancellation_email(
                is_client=False,
                appointment=appointment,
                client_name=client.full_name or client.email,
                cancelled_by_client=canceller_is_client
            )
            send_email(
                email_to=nutritionist.email,
                subject=nutritionist_email_data.subject,
                html_content=nutritionist_email_data.html_content
            )
    except Exception:
        # If email sending fails, continue anyway
        pass

    return Message(message="Appointment cancelled successfully")