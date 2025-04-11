import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from sqlmodel import Session, select, or_

from app.core.security import get_password_hash, verify_password
from app.models import (
    Item, ItemCreate, User, UserCreate, UserUpdate,
    Profile, ProfileCreate, ProfileUpdate,
    Availability, AvailabilityCreate, AvailabilityUpdate,
    Appointment, AppointmentCreate, AppointmentUpdate, AppointmentStatus,
    NutritionRecord, NutritionRecordCreate, NutritionRecordUpdate,
    UserType
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> Optional[User]:
    statement = select(User).where(User.id == user_id)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def get_users(
        *, session: Session, skip: int = 0, limit: int = 100, user_type: Optional[UserType] = None
) -> List[User]:
    statement = select(User)
    if user_type:
        statement = statement.where(User.user_type == user_type)
    statement = statement.offset(skip).limit(limit)
    return session.exec(statement).all()


def get_users_count(*, session: Session, user_type: Optional[UserType] = None) -> int:
    statement = select(User)
    if user_type:
        statement = statement.where(User.user_type == user_type)
    return len(session.exec(statement).all())


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


# Profile

def create_profile(*, session: Session, profile_in: ProfileCreate, user_id: uuid.UUID) -> Profile:
    """Create a new profile for a user."""
    now = datetime.now(timezone.utc).date()
    db_profile = Profile.model_validate(
        profile_in, update={
            "user_id": user_id,
            "created_at": now,
            "updated_at": now
        }
    )
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


def update_profile(*, session: Session, db_profile: Profile, profile_in: ProfileUpdate) -> Profile:
    """Update a user's profile."""
    profile_data = profile_in.model_dump(exclude_unset=True)
    profile_data["updated_at"] = datetime.now(timezone.utc).date()
    db_profile.sqlmodel_update(profile_data)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


def get_profile_by_user_id(*, session: Session, user_id: uuid.UUID) -> Optional[Profile]:
    """Get a user's profile by user ID."""
    statement = select(Profile).where(Profile.user_id == user_id)
    return session.exec(statement).first()


def get_profile_by_id(*, session: Session, profile_id: uuid.UUID) -> Optional[Profile]:
    """Get a profile by profile ID."""
    return session.get(Profile, profile_id)


# Availability

def create_availability(
        *, session: Session, availability_in: AvailabilityCreate, nutritionist_id: uuid.UUID
) -> Availability:
    """Create a new availability slot for a nutritionist."""
    now = datetime.now(timezone.utc).date()
    db_availability = Availability.model_validate(
        availability_in, update={
            "nutritionist_id": nutritionist_id,
            "created_at": now,
            "updated_at": now
        }
    )
    session.add(db_availability)
    session.commit()
    session.refresh(db_availability)
    return db_availability


def update_availability(
        *, session: Session, db_availability: Availability, availability_in: AvailabilityUpdate
) -> Availability:
    """Update an availability slot."""
    availability_data = availability_in.model_dump(exclude_unset=True)
    availability_data["updated_at"] = datetime.now(timezone.utc).date()
    db_availability.sqlmodel_update(availability_data)
    session.add(db_availability)
    session.commit()
    session.refresh(db_availability)
    return db_availability


def get_availability_by_id(*, session: Session, availability_id: uuid.UUID) -> Optional[Availability]:
    """Get an availability slot by ID."""
    return session.get(Availability, availability_id)


def get_availabilities_by_nutritionist(
        *, session: Session, nutritionist_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[Availability]:
    """Get all availability slots for a nutritionist."""
    statement = select(Availability).where(
        Availability.nutritionist_id == nutritionist_id
    ).offset(skip).limit(limit)
    return session.exec(statement).all()


def get_availabilities_count_by_nutritionist(*, session: Session, nutritionist_id: uuid.UUID) -> int:
    """Get count of availability slots for a nutritionist."""
    statement = select(Availability).where(Availability.nutritionist_id == nutritionist_id)
    return len(session.exec(statement).all())


def get_availabilities_by_date_range(
        *, session: Session, nutritionist_id: uuid.UUID, start_date: date, end_date: date
) -> List[Availability]:
    """Get availability slots for a nutritionist within a date range."""
    statement = select(Availability).where(
        Availability.nutritionist_id == nutritionist_id,
        or_(
            # For recurring slots (need to check day of week)
            Availability.is_recurring == True,
            # For specific date slots
            (
                Availability.is_recurring == False,
                Availability.specific_date >= start_date,
                Availability.specific_date <= end_date
            )
        )
    )
    return session.exec(statement).all()


def delete_availability(*, session: Session, availability_id: uuid.UUID) -> None:
    """Delete an availability slot."""
    availability = session.get(Availability, availability_id)
    if availability:
        session.delete(availability)
        session.commit()


# Appointment

def create_appointment(
        *, session: Session, appointment_in: AppointmentCreate, client_id: uuid.UUID
) -> Appointment:
    """Create a new appointment."""
    now = datetime.now(timezone.utc).date()
    db_appointment = Appointment.model_validate(
        appointment_in, update={
            "client_id": client_id,
            "created_at": now,
            "updated_at": now
        }
    )
    session.add(db_appointment)
    session.commit()
    session.refresh(db_appointment)
    return db_appointment


def update_appointment(
        *, session: Session, db_appointment: Appointment, appointment_in: AppointmentUpdate
) -> Appointment:
    """Update an appointment."""
    appointment_data = appointment_in.model_dump(exclude_unset=True)
    appointment_data["updated_at"] = datetime.now(timezone.utc).date()
    db_appointment.sqlmodel_update(appointment_data)
    session.add(db_appointment)
    session.commit()
    session.refresh(db_appointment)
    return db_appointment


def get_appointment_by_id(*, session: Session, appointment_id: uuid.UUID) -> Optional[Appointment]:
    """Get an appointment by ID."""
    return session.get(Appointment, appointment_id)


def get_appointments_by_client(
        *, session: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[Appointment]:
    """Get all appointments for a client."""
    statement = select(Appointment).where(
        Appointment.client_id == client_id
    ).offset(skip).limit(limit).order_by(Appointment.date, Appointment.start_time)
    return session.exec(statement).all()


def get_appointments_count_by_client(*, session: Session, client_id: uuid.UUID) -> int:
    """Get count of appointments for a client."""
    statement = select(Appointment).where(Appointment.client_id == client_id)
    return len(session.exec(statement).all())


def get_appointments_by_nutritionist(
        *, session: Session, nutritionist_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[Appointment]:
    """Get all appointments for a nutritionist."""
    statement = select(Appointment).where(
        Appointment.nutritionist_id == nutritionist_id
    ).offset(skip).limit(limit).order_by(Appointment.date, Appointment.start_time)
    return session.exec(statement).all()


def get_appointments_count_by_nutritionist(*, session: Session, nutritionist_id: uuid.UUID) -> int:
    """Get count of appointments for a nutritionist."""
    statement = select(Appointment).where(Appointment.nutritionist_id == nutritionist_id)
    return len(session.exec(statement).all())


def get_appointments_by_date_range(
        *,
        session: Session,
        nutritionist_id: Optional[uuid.UUID] = None,
        client_id: Optional[uuid.UUID] = None,
        start_date: date,
        end_date: date,
        status: Optional[AppointmentStatus] = None
) -> List[Appointment]:
    """Get appointments within a date range, filtered by user and status."""
    statement = select(Appointment).where(
        Appointment.date >= start_date,
        Appointment.date <= end_date
    )

    if nutritionist_id:
        statement = statement.where(Appointment.nutritionist_id == nutritionist_id)

    if client_id:
        statement = statement.where(Appointment.client_id == client_id)

    if status:
        statement = statement.where(Appointment.status == status)

    statement = statement.order_by(Appointment.date, Appointment.start_time)
    return session.exec(statement).all()


def cancel_appointment(*, session: Session, appointment_id: uuid.UUID) -> Optional[Appointment]:
    """Cancel an appointment by setting its status to cancelled."""
    appointment = session.get(Appointment, appointment_id)
    if appointment:
        appointment.status = AppointmentStatus.CANCELLED
        appointment.updated_at = datetime.now(timezone.utc).date()
        session.add(appointment)
        session.commit()
        session.refresh(appointment)
    return appointment


# Nutrition Record

def create_nutrition_record(
        *,
        session: Session,
        record_in: NutritionRecordCreate,
        created_by_id: uuid.UUID
) -> NutritionRecord:
    """Create a new nutrition record."""
    now = datetime.now(timezone.utc).date()
    db_record = NutritionRecord.model_validate(
        record_in, update={
            "created_by_id": created_by_id,
            "created_at": now,
            "updated_at": now
        }
    )
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def update_nutrition_record(
        *, session: Session, db_record: NutritionRecord, record_in: NutritionRecordUpdate
) -> NutritionRecord:
    """Update a nutrition record."""
    record_data = record_in.model_dump(exclude_unset=True)
    record_data["updated_at"] = datetime.now(timezone.utc).date()
    db_record.sqlmodel_update(record_data)
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def get_nutrition_record_by_id(*, session: Session, record_id: uuid.UUID) -> Optional[NutritionRecord]:
    """Get a nutrition record by ID."""
    return session.get(NutritionRecord, record_id)


def get_nutrition_records_by_client(
        *, session: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[NutritionRecord]:
    """Get all nutrition records for a client."""
    statement = select(NutritionRecord).where(
        NutritionRecord.client_id == client_id
    ).offset(skip).limit(limit).order_by(NutritionRecord.date.desc())
    return session.exec(statement).all()


def get_nutrition_records_count_by_client(*, session: Session, client_id: uuid.UUID) -> int:
    """Get count of nutrition records for a client."""
    statement = select(NutritionRecord).where(NutritionRecord.client_id == client_id)
    return len(session.exec(statement).all())


def get_nutrition_records_by_date_range(
        *, session: Session, client_id: uuid.UUID, start_date: date, end_date: date
) -> List[NutritionRecord]:
    """Get nutrition records for a client within a date range."""
    statement = select(NutritionRecord).where(
        NutritionRecord.client_id == client_id,
        NutritionRecord.date >= start_date,
        NutritionRecord.date <= end_date
    ).order_by(NutritionRecord.date.desc())
    return session.exec(statement).all()


def delete_nutrition_record(*, session: Session, record_id: uuid.UUID) -> None:
    """Delete a nutrition record."""
    record = session.get(NutritionRecord, record_id)
    if record:
        session.delete(record)
        session.commit()
