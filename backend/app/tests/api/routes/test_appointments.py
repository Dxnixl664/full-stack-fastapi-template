import uuid
from datetime import date, time, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import (
    User, UserCreate, UserType,
    Appointment, AppointmentCreate, AppointmentStatus,
    Availability, AvailabilityCreate
)
from app.tests.utils.utils import random_lower_string, random_email


def create_test_nutritionist(db: Session) -> User:
    """Create a test nutritionist user"""
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(
        email=email,
        password=password,
        user_type=UserType.NUTRITIONIST
    )
    user = crud.create_user(session=db, user_create=user_in)
    return user


def create_test_availability(db: Session, nutritionist_id: uuid.UUID) -> Availability:
    """Create availability for a nutritionist for tomorrow"""
    tomorrow = date.today() + timedelta(days=1)
    weekday = tomorrow.weekday()

    availability_in = AvailabilityCreate(
        day_of_week=weekday,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_recurring=True
    )

    availability = crud.create_availability(
        session=db,
        availability_in=availability_in,
        nutritionist_id=nutritionist_id
    )

    return availability


def create_test_appointment(
        db: Session, client_id: uuid.UUID, nutritionist_id: uuid.UUID
) -> Appointment:
    """Create a test appointment for tomorrow"""
    tomorrow = date.today() + timedelta(days=1)

    appointment_in = AppointmentCreate(
        nutritionist_id=nutritionist_id,
        date=tomorrow,
        start_time=time(10, 0),
        end_time=time(11, 0),
        notes="Test appointment"
    )

    appointment = crud.create_appointment(
        session=db,
        appointment_in=appointment_in,
        client_id=client_id
    )

    return appointment


def test_create_appointment(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a new appointment"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Appointment data
    tomorrow = date.today() + timedelta(days=1)
    appointment_data = {
        "nutritionist_id": str(nutritionist.id),
        "date": tomorrow.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "notes": "Test appointment"
    }

    # Create the appointment
    with patch("app.utils.send_email", return_value=None):
        response = client.post(
            f"{settings.API_V1_STR}/appointments/",
            headers=normal_user_token_headers,
            json=appointment_data
        )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["nutritionist_id"] == str(nutritionist.id)
    assert data["date"] == tomorrow.isoformat()
    assert data["start_time"] == "10:00:00"
    assert data["end_time"] == "11:00:00"
    assert data["notes"] == "Test appointment"
    assert data["status"] == AppointmentStatus.SCHEDULED

    # Check database
    appointment = db.get(Appointment, uuid.UUID(data["id"]))
    assert appointment is not None
    assert appointment.nutritionist_id == nutritionist.id
    assert appointment.date == tomorrow
    assert appointment.status == AppointmentStatus.SCHEDULED


def test_create_appointment_invalid_nutritionist(
        client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Test creating an appointment with an invalid nutritionist"""
    # Appointment data with a non-existent nutritionist
    tomorrow = date.today() + timedelta(days=1)
    appointment_data = {
        "nutritionist_id": str(uuid.uuid4()),
        "date": tomorrow.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "notes": "Test appointment"
    }

    # Create the appointment
    response = client.post(
        f"{settings.API_V1_STR}/appointments/",
        headers=normal_user_token_headers,
        json=appointment_data
    )

    # Check response
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Nutritionist not found"


def test_create_appointment_invalid_time_range(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating an appointment with an invalid time range"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Appointment data with end time before start time
    tomorrow = date.today() + timedelta(days=1)
    appointment_data = {
        "nutritionist_id": str(nutritionist.id),
        "date": tomorrow.isoformat(),
        "start_time": "11:00:00",
        "end_time": "10:00:00",
        "notes": "Test appointment"
    }

    # Create the appointment
    response = client.post(
        f"{settings.API_V1_STR}/appointments/",
        headers=normal_user_token_headers,
        json=appointment_data
    )

    # Check response
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "End time must be after start time"


def test_create_appointment_past_date(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating an appointment in the past"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Appointment data with past date
    yesterday = date.today() - timedelta(days=1)
    appointment_data = {
        "nutritionist_id": str(nutritionist.id),
        "date": yesterday.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "notes": "Test appointment"
    }

    # Create the appointment
    response = client.post(
        f"{settings.API_V1_STR}/appointments/",
        headers=normal_user_token_headers,
        json=appointment_data
    )

    # Check response
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Appointment time must be in the future"


def test_create_appointment_time_conflict(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating an appointment with a time conflict"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create a first appointment
    tomorrow = date.today() + timedelta(days=1)
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    first_appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Try to create a second appointment at the same time
    appointment_data = {
        "nutritionist_id": str(nutritionist.id),
        "date": tomorrow.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "notes": "Test appointment"
    }

    # Create the second appointment
    response = client.post(
        f"{settings.API_V1_STR}/appointments/",
        headers=normal_user_token_headers,
        json=appointment_data
    )

    # Check response
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "The selected time slot is already booked"


def test_get_appointments(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test getting all appointments for the current user"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Get appointments
    response = client.get(
        f"{settings.API_V1_STR}/appointments/",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1
    assert "count" in data
    assert data["count"] >= 1

    # Check that the appointment we created is in the response
    appointment_in_response = False
    for appt in data["data"]:
        if appt["id"] == str(appointment.id):
            appointment_in_response = True
            break
    assert appointment_in_response


def test_get_appointments_with_status_filter(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test getting appointments filtered by status"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create a scheduled appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    scheduled_appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Create a cancelled appointment
    cancelled_appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )
    cancelled_appointment.status = AppointmentStatus.CANCELLED
    db.add(cancelled_appointment)
    db.commit()

    # Get only scheduled appointments
    response = client.get(
        f"{settings.API_V1_STR}/appointments/?status=scheduled",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1

    # Check that all appointments have the scheduled status
    for appt in data["data"]:
        assert appt["status"] == AppointmentStatus.SCHEDULED

    # Get only cancelled appointments
    response = client.get(
        f"{settings.API_V1_STR}/appointments/?status=cancelled",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1

    # Check that all appointments have the cancelled status
    for appt in data["data"]:
        assert appt["status"] == AppointmentStatus.CANCELLED


def test_get_appointments_by_date_range(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test getting appointments within a date range"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment for tomorrow
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    tomorrow = date.today() + timedelta(days=1)
    appointment_tomorrow = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Create an appointment for day after tomorrow
    day_after_tomorrow = date.today() + timedelta(days=2)

    # For this appointment, we need to create a new availability first
    weekday = day_after_tomorrow.weekday()
    availability_in = AvailabilityCreate(
        day_of_week=weekday,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_recurring=True
    )

    another_availability = crud.create_availability(
        session=db,
        availability_in=availability_in,
        nutritionist_id=nutritionist.id
    )

    appointment_in = AppointmentCreate(
        nutritionist_id=nutritionist.id,
        date=day_after_tomorrow,
        start_time=time(10, 0),
        end_time=time(11, 0),
        notes="Test appointment for day after tomorrow"
    )

    appointment_day_after = crud.create_appointment(
        session=db,
        appointment_in=appointment_in,
        client_id=current_user.id
    )

    # Get appointments for tomorrow only
    start_date = tomorrow.isoformat()
    end_date = tomorrow.isoformat()
    response = client.get(
        f"{settings.API_V1_STR}/appointments/date-range?start_date={start_date}&end_date={end_date}",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

    # Check that all appointments are on tomorrow's date
    for appt in data:
        assert appt["date"] == tomorrow.isoformat()

    # Get appointments for tomorrow and day after tomorrow
    start_date = tomorrow.isoformat()
    end_date = day_after_tomorrow.isoformat()
    response = client.get(
        f"{settings.API_V1_STR}/appointments/date-range?start_date={start_date}&end_date={end_date}",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

    # Check that all appointments are within the date range
    for appt in data:
        appt_date = date.fromisoformat(appt["date"])
        assert appt_date >= tomorrow and appt_date <= day_after_tomorrow


def test_get_specific_appointment(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test getting a specific appointment"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Get the appointment
    response = client.get(
        f"{settings.API_V1_STR}/appointments/{appointment.id}",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(appointment.id)
    assert data["nutritionist_id"] == str(nutritionist.id)
    assert data["date"] == appointment.date.isoformat()
    assert data["start_time"] == appointment.start_time.isoformat()
    assert data["end_time"] == appointment.end_time.isoformat()
    assert data["notes"] == appointment.notes
    assert data["status"] == appointment.status


def test_get_specific_appointment_not_found(
        client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Test getting a non-existent appointment"""
    # Generate a random UUID
    random_id = uuid.uuid4()

    # Try to get a non-existent appointment
    response = client.get(
        f"{settings.API_V1_STR}/appointments/{random_id}",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Appointment not found"


def test_update_appointment(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating an appointment"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Update data
    update_data = {
        "notes": "Updated test appointment",
        "start_time": "10:30:00",
        "end_time": "11:30:00"
    }

    # Update the appointment
    with patch("app.utils.send_email", return_value=None):
        response = client.patch(
            f"{settings.API_V1_STR}/appointments/{appointment.id}",
            headers=normal_user_token_headers,
            json=update_data
        )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(appointment.id)
    assert data["notes"] == "Updated test appointment"
    assert data["start_time"] == "10:30:00"
    assert data["end_time"] == "11:30:00"

    # Check database
    db.expire_all()
    updated_appointment = db.get(Appointment, appointment.id)
    assert updated_appointment is not None
    assert updated_appointment.notes == "Updated test appointment"
    assert updated_appointment.start_time == time(10, 30)
    assert updated_appointment.end_time == time(11, 30)


def test_update_appointment_invalid_time_range(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating an appointment with an invalid time range"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Update data with end time before start time
    update_data = {
        "start_time": "11:00:00",
        "end_time": "10:00:00"
    }

    # Try to update the appointment
    response = client.patch(
        f"{settings.API_V1_STR}/appointments/{appointment.id}",
        headers=normal_user_token_headers,
        json=update_data
    )

    # Check response
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "End time must be after start time"


def test_cancel_appointment(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test cancelling an appointment"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Cancel the appointment
    with patch("app.utils.send_email", return_value=None):
        response = client.delete(
            f"{settings.API_V1_STR}/appointments/{appointment.id}",
            headers=normal_user_token_headers
        )

    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Appointment cancelled successfully"

    # Check database
    db.expire_all()
    cancelled_appointment = db.get(Appointment, appointment.id)
    assert cancelled_appointment is not None
    assert cancelled_appointment.status == AppointmentStatus.CANCELLED


def test_cancel_already_cancelled_appointment(
        client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test cancelling an already cancelled appointment"""
    # Create a nutritionist
    nutritionist = create_test_nutritionist(db)

    # Create availability for the nutritionist
    availability = create_test_availability(db, nutritionist.id)

    # Create an appointment
    statement = select(User).where(User.email == settings.EMAIL_TEST_USER)
    current_user = db.exec(statement).first()

    appointment = create_test_appointment(
        db=db,
        client_id=current_user.id,
        nutritionist_id=nutritionist.id
    )

    # Cancel the appointment first
    appointment.status = AppointmentStatus.CANCELLED
    db.add(appointment)
    db.commit()

    # Try to cancel it again
    response = client.delete(
        f"{settings.API_V1_STR}/appointments/{appointment.id}",
        headers=normal_user_token_headers
    )

    # Check response
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Appointment is already cancelled"