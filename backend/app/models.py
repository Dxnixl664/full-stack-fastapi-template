import uuid
from datetime import date, time
from enum import Enum
from typing import List, Optional

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


# Enums for constrained fields
class UserType(str, Enum):
    CLIENT = "client"
    NUTRITIONIST = "nutritionist"
    ADMIN = "admin"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    user_type: UserType = Field(default=UserType.CLIENT)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)
    user_type: UserType = Field(default=UserType.CLIENT)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)
    user_type: Optional[UserType] = None


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    profile: Optional["Profile"] = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})
    appointments_as_client: List["Appointment"] = Relationship(
        back_populates="client",
        sa_relationship_kwargs={"foreign_keys": "Appointment.client_id"},
        cascade_delete=True
    )
    appointments_as_nutritionist: List["Appointment"] = Relationship(
        back_populates="nutritionist",
        sa_relationship_kwargs={"foreign_keys": "Appointment.nutritionist_id"},
        cascade_delete=True
    )
    availabilities: List["Availability"] = Relationship(
        back_populates="nutritionist",
        cascade_delete=True
    )
    nutrition_records: List["NutritionRecord"] = Relationship(
        back_populates="client",
        sa_relationship_kwargs={"foreign_keys": "NutritionRecord.client_id"},
        cascade_delete=True
    )
    created_records: List["NutritionRecord"] = Relationship(
        back_populates="created_by",
        sa_relationship_kwargs={"foreign_keys": "NutritionRecord.created_by_id"},
        cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Profile models
class ProfileBase(SQLModel):
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=255)
    date_of_birth: Optional[date] = None
    bio: Optional[str] = Field(default=None, max_length=1000)
    specialization: Optional[str] = Field(default=None, max_length=255)
    years_of_experience: Optional[int] = None
    profile_image: Optional[str] = Field(default=None, max_length=255)


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class Profile(ProfileBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    user: User = Relationship(back_populates="profile")
    created_at: Optional[date] = Field(default=None)
    updated_at: Optional[date] = Field(default=None)


class ProfilePublic(ProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID


# Availability models
class AvailabilityBase(SQLModel):
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: time
    end_time: time
    is_recurring: bool = True
    specific_date: Optional[date] = None


class AvailabilityCreate(AvailabilityBase):
    pass


class AvailabilityUpdate(AvailabilityBase):
    pass


class Availability(AvailabilityBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nutritionist_id: uuid.UUID = Field(foreign_key="user.id")
    nutritionist: User = Relationship(back_populates="availabilities")
    created_at: Optional[date] = Field(default=None)
    updated_at: Optional[date] = Field(default=None)


class AvailabilityPublic(AvailabilityBase):
    id: uuid.UUID
    nutritionist_id: uuid.UUID


# Appointment models
class AppointmentBase(SQLModel):
    date: date
    start_time: time
    end_time: time
    status: AppointmentStatus = Field(default=AppointmentStatus.SCHEDULED)
    notes: Optional[str] = Field(default=None, max_length=1000)


class AppointmentCreate(AppointmentBase):
    nutritionist_id: uuid.UUID


class AppointmentUpdate(SQLModel):
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class Appointment(AppointmentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="user.id")
    nutritionist_id: uuid.UUID = Field(foreign_key="user.id")
    client: User = Relationship(
        back_populates="appointments_as_client",
        sa_relationship_kwargs={"foreign_keys": "Appointment.client_id"}
    )
    nutritionist: User = Relationship(
        back_populates="appointments_as_nutritionist",
        sa_relationship_kwargs={"foreign_keys": "Appointment.nutritionist_id"}
    )
    created_at: Optional[date] = Field(default=None)
    updated_at: Optional[date] = Field(default=None)


class AppointmentPublic(AppointmentBase):
    id: uuid.UUID
    client_id: uuid.UUID
    nutritionist_id: uuid.UUID


class AppointmentsPublic(SQLModel):
    data: List[AppointmentPublic]
    count: int


# Nutrition record models
class NutritionRecordBase(SQLModel):
    date: date
    weight: Optional[float] = None
    height: Optional[float] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    recommendations: Optional[str] = Field(default=None, max_length=1000)


class NutritionRecordCreate(NutritionRecordBase):
    client_id: uuid.UUID


class NutritionRecordUpdate(SQLModel):
    date: Optional[date] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    recommendations: Optional[str] = Field(default=None, max_length=1000)


class NutritionRecord(NutritionRecordBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="user.id")
    created_by_id: uuid.UUID = Field(foreign_key="user.id")
    client: User = Relationship(
        back_populates="nutrition_records",
        sa_relationship_kwargs={"foreign_keys": "NutritionRecord.client_id"}
    )
    created_by: User = Relationship(
        back_populates="created_records",
        sa_relationship_kwargs={"foreign_keys": "NutritionRecord.created_by_id"}
    )
    created_at: Optional[date] = Field(default=None)
    updated_at: Optional[date] = Field(default=None)

    @property
    def bmi(self) -> Optional[float]:
        """Calculate BMI if height and weight are provided."""
        if self.height and self.weight and self.height > 0:
            # Height in meters, weight in kg
            return self.weight / (self.height ** 2)
        return None


class NutritionRecordPublic(NutritionRecordBase):
    id: uuid.UUID
    client_id: uuid.UUID
    created_by_id: uuid.UUID
    bmi: Optional[float] = None


class NutritionRecordsPublic(SQLModel):
    data: List[NutritionRecordPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
