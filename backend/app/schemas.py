from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least two characters")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=10, max_length=8192)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    email_verified: bool
    is_suspended: bool
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AuthMessageOut(BaseModel):
    message: str


class EmailActionRequest(BaseModel):
    email: EmailStr


class AuthTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class PasswordResetRequest(AuthTokenRequest):
    password: str = Field(min_length=12, max_length=128)


class PetBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    species: str = Field(min_length=1, max_length=40)
    breed: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    sex: str | None = Field(default=None, max_length=20)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    allergies: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    photo_url: str | None = Field(default=None, max_length=500)


class PetCreate(PetBase):
    pass


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    species: str | None = Field(default=None, min_length=1, max_length=40)
    breed: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    sex: str | None = Field(default=None, max_length=20)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    allergies: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    photo_url: str | None = Field(default=None, max_length=500)


class PetOut(PetBase):
    id: int
    archived: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicalRecordCreate(BaseModel):
    record_type: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    details: str = Field(min_length=1, max_length=4000)
    recorded_at: datetime | None = None


class MedicalRecordOut(MedicalRecordCreate):
    id: int
    pet_id: int
    professional_record: bool
    model_config = ConfigDict(from_attributes=True)


class CareTaskCreate(BaseModel):
    pet_id: int
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(default="care", min_length=2, max_length=40)
    instructions: str | None = Field(default=None, max_length=500)
    due_at: datetime
    repeat_interval_minutes: int | None = Field(default=None, ge=1, le=525600)
    reminder_days_before: int = Field(default=1, ge=0, le=30)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A title is required")
        return value

    @field_validator("instructions")
    @classmethod
    def clean_instructions(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class CareTaskOut(CareTaskCreate):
    id: int
    completed: bool
    reminder_sent_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class AdoptionListingCreate(BaseModel):
    pet_name: str = Field(min_length=1, max_length=80)
    species: str = Field(min_length=1, max_length=40)
    breed: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=10, max_length=3000)
    service_area: str = Field(min_length=2, max_length=160)


class AdoptionListingStatus(BaseModel):
    status: Literal["available", "pending", "adopted", "withdrawn"]


class AdoptionListingOut(AdoptionListingCreate):
    id: int
    shelter_user_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MissingPetCreate(BaseModel):
    pet_id: int | None = None
    pet_name: str = Field(default="", max_length=80)
    species: str = Field(default="", max_length=40)
    description: str = Field(min_length=10, max_length=3000)
    service_area: str = Field(min_length=2, max_length=160)
    contact_instructions: str = Field(min_length=3, max_length=240)


class MissingPetStatus(BaseModel):
    status: Literal["missing", "found", "closed"]


class MissingPetOut(MissingPetCreate):
    id: int
    owner_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PetSightingCreate(BaseModel):
    description: str = Field(min_length=5, max_length=1000)
    service_area: str = Field(min_length=2, max_length=160)


class PetSightingOut(PetSightingCreate):
    id: int
    report_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CareAssistantRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    pet_species: str | None = Field(default=None, max_length=40)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Please enter a little more detail")
        return value


class CareAssistantResponse(BaseModel):
    answer: str
    urgent: bool = False


class DashboardOut(BaseModel):
    role: str
    pet_count: int
    due_tasks: int
    completed_tasks: int
    recent_records: int
    upcoming_tasks: list[CareTaskOut]
    pending_appointments: int = 0
    active_appointments: int = 0
    active_emergencies: int = 0
    pending_applications: int = 0
    suspended_users: int = 0


class ProfessionalApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_role: Literal["veterinarian", "groomer", "shelter", "volunteer"]
    organization_name: str = Field(min_length=2, max_length=160)
    credential_summary: str = Field(min_length=20, max_length=4000)

    @field_validator("organization_name", "credential_summary")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class ProfessionalApplicationOut(BaseModel):
    id: int
    user_id: int
    requested_role: str
    organization_name: str
    credential_summary: str
    status: str
    review_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ProfessionalApplicationReview(BaseModel):
    decision: Literal["approved", "rejected"]
    review_notes: str | None = Field(default=None, max_length=2000)


class AdminUserOut(UserOut):
    created_at: datetime


class ProviderProfileCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    bio: str = Field(min_length=10, max_length=3000)
    service_area: str | None = Field(default=None, max_length=160)
    service_fee: float = Field(default=0, ge=0, le=100000)

    @field_validator("display_name", "bio")
    @classmethod
    def strip_provider_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class ProviderProfileOut(BaseModel):
    id: int
    user_id: int
    kind: str
    display_name: str
    bio: str
    service_area: str | None
    service_fee: float
    model_config = ConfigDict(from_attributes=True)


class AvailabilityCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("A timezone is required")
        return value


class AvailabilityOut(BaseModel):
    id: int
    provider_id: int
    starts_at: datetime
    ends_at: datetime
    is_available: bool
    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    pet_id: int
    availability_id: int
    owner_note: str | None = Field(default=None, max_length=2000)


class AppointmentOut(BaseModel):
    id: int
    owner_id: int
    pet_id: int
    provider_id: int
    availability_id: int
    service_kind: str
    status: str
    owner_note: str | None
    created_at: datetime
    starts_at: datetime
    ends_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AppointmentReview(BaseModel):
    status: Literal["confirmed", "rejected", "completed", "cancelled"]


class AppointmentReschedule(BaseModel):
    availability_id: int


class EmergencyRequestCreate(BaseModel):
    category: Literal[
        "breathing_difficulty",
        "suspected_poisoning",
        "serious_injury",
        "severe_bleeding",
        "seizure",
        "heat_emergency",
        "road_accident",
        "missing_pet",
        "injured_stray",
        "other",
    ]
    severity: Literal["critical", "urgent"]
    description: str = Field(min_length=5, max_length=4000)
    pet_id: int | None = None
    location: str | None = Field(default=None, max_length=400)

    @field_validator("description", "location")
    @classmethod
    def clean_emergency_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value and value is not None:
            raise ValueError("This field cannot be blank")
        return value


class EmergencyRequestOut(BaseModel):
    id: int
    owner_id: int
    pet_id: int | None
    category: str
    severity: str
    description: str
    location: str | None
    assigned_volunteer_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmergencyStatusUpdate(BaseModel):
    status: Literal["responding", "in_progress", "completed", "cancelled", "escalated"]


class VolunteerProfileUpdate(BaseModel):
    service_area: str | None = Field(default=None, max_length=160)
    is_available: bool

    @field_validator("service_area")
    @classmethod
    def clean_service_area(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class VolunteerProfileOut(BaseModel):
    id: int
    user_id: int
    service_area: str | None
    is_available: bool
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    kind: str
    message: str
    emergency_request_id: int | None
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    context_type: Literal["appointment", "emergency"]
    context_id: int = Field(gt=0)


class ConversationOut(BaseModel):
    id: int
    appointment_id: int | None
    emergency_request_id: int | None
    other_user_id: int
    other_user_name: str
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    updated_at: datetime


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str
    body: str
    created_at: datetime
    read_at: datetime | None
