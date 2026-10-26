from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, false, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="owner", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    pets: Mapped[list["Pet"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    professional_applications: Mapped[list["ProfessionalApplication"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="ProfessionalApplication.user_id",
    )


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index("ix_auth_tokens_user_purpose", "user_id", "purpose", "used_at", "expires_at"),
        UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
        CheckConstraint("purpose IN ('email_verification', 'password_reset')", name="ck_auth_tokens_purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProfessionalApplication(Base):
    __tablename__ = "professional_applications"
    __table_args__ = (
        CheckConstraint(
            "requested_role IN ('veterinarian', 'groomer', 'shelter', 'volunteer')",
            name="ck_professional_applications_requested_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_professional_applications_status",
        ),
        Index(
            "uq_professional_applications_pending_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_professional_applications_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requested_role: Mapped[str] = mapped_column(String(24), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(160), nullable=False)
    credential_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="professional_applications", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"
    __table_args__ = (
        CheckConstraint("kind IN ('veterinarian', 'groomer')", name="ck_provider_profiles_kind"),
        CheckConstraint("service_fee >= 0", name="ck_provider_profiles_service_fee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    service_area: Mapped[str | None] = mapped_column(String(160))
    service_fee: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ProviderAvailability(Base):
    __tablename__ = "provider_availability"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_provider_availability_start_before_end"),
        UniqueConstraint("provider_id", "starts_at", name="uq_provider_availability_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'completed', 'cancelled')",
            name="ck_appointments_status",
        ),
        CheckConstraint(
            "service_kind IN ('veterinarian', 'groomer')",
            name="ck_appointments_service_kind",
        ),
        Index(
            "uq_appointments_active_slot",
            "availability_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'confirmed')"),
            postgresql_where=text("status IN ('pending', 'confirmed')"),
        ),
        Index("ix_appointments_owner_created", "owner_id", "created_at"),
        Index("ix_appointments_provider_created", "provider_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    availability_id: Mapped[int] = mapped_column(
        ForeignKey("provider_availability.id", ondelete="RESTRICT"), nullable=False
    )
    service_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    owner_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    availability: Mapped[ProviderAvailability] = relationship()

    @property
    def starts_at(self) -> datetime:
        return self.availability.starts_at

    @property
    def ends_at(self) -> datetime:
        return self.availability.ends_at


class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"
    __table_args__ = (Index("ix_volunteer_profiles_available", "is_available", "service_area"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    service_area: Mapped[str | None] = mapped_column(String(160))
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmergencyRequest(Base):
    __tablename__ = "emergency_requests"
    __table_args__ = (
        CheckConstraint(
            "category IN ('breathing_difficulty', 'suspected_poisoning', 'serious_injury', "
            "'severe_bleeding', 'seizure', 'heat_emergency', 'road_accident', 'missing_pet', "
            "'injured_stray', 'other')",
            name="ck_emergency_requests_category",
        ),
        CheckConstraint("severity IN ('critical', 'urgent')", name="ck_emergency_requests_severity"),
        CheckConstraint(
            "status IN ('submitted', 'assigned', 'responding', 'in_progress', 'completed', 'cancelled', 'escalated')",
            name="ck_emergency_requests_status",
        ),
        Index(
            "uq_emergency_active_volunteer_assignment",
            "assigned_volunteer_id",
            unique=True,
            sqlite_where=text(
                "assigned_volunteer_id IS NOT NULL AND status IN ('assigned', 'responding', 'in_progress')"
            ),
            postgresql_where=text(
                "assigned_volunteer_id IS NOT NULL AND status IN ('assigned', 'responding', 'in_progress')"
            ),
        ),
        Index("ix_emergency_requests_status_created", "status", "created_at"),
        Index("ix_emergency_requests_owner_created", "owner_id", "created_at"),
        Index("ix_emergency_requests_volunteer_created", "assigned_volunteer_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_id: Mapped[int | None] = mapped_column(ForeignKey("pets.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(400))
    assigned_volunteer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="submitted", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmergencyDecline(Base):
    __tablename__ = "emergency_declines"
    __table_args__ = (
        UniqueConstraint("emergency_request_id", "volunteer_user_id", name="uq_emergency_decline_volunteer"),
        Index("ix_emergency_declines_volunteer_created", "volunteer_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_request_id: Mapped[int] = mapped_column(
        ForeignKey("emergency_requests.id", ondelete="CASCADE"), nullable=False
    )
    volunteer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
        Index("ix_notifications_user_unread_created", "user_id", "is_read", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    emergency_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("emergency_requests.id", ondelete="CASCADE")
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "(appointment_id IS NOT NULL AND emergency_request_id IS NULL) OR "
            "(appointment_id IS NULL AND emergency_request_id IS NOT NULL)",
            name="ck_conversations_one_context",
        ),
        UniqueConstraint("appointment_id", name="uq_conversations_appointment"),
        UniqueConstraint("emergency_request_id", name="uq_conversations_emergency"),
        Index("ix_conversations_updated", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"))
    emergency_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("emergency_requests.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
        Index("ix_conversation_participants_user", "user_id", "conversation_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Pet(Base):
    __tablename__ = "pets"
    __table_args__ = (Index("ix_pets_owner_archived", "owner_id", "archived"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    species: Mapped[str] = mapped_column(String(40), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(20))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    allergies: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    owner: Mapped[User] = relationship(back_populates="pets")
    records: Mapped[list["MedicalRecord"]] = relationship(cascade="all, delete-orphan")
    care_tasks: Mapped[list["CareTask"]] = relationship(cascade="all, delete-orphan")


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    __table_args__ = (Index("ix_medical_records_pet_recorded", "pet_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    professional_record: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CareTask(Base):
    __tablename__ = "care_tasks"
    __table_args__ = (
        Index("ix_care_tasks_pet_due", "pet_id", "due_at"),
        Index("ix_care_tasks_reminders", "completed", "reminder_sent_at", "due_at"),
        CheckConstraint(
            "repeat_interval_minutes IS NULL OR repeat_interval_minutes BETWEEN 1 AND 525600",
            name="ck_care_tasks_repeat_interval",
        ),
        CheckConstraint("reminder_days_before BETWEEN 0 AND 30", name="ck_care_tasks_reminder_days"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="care", nullable=False)
    instructions: Mapped[str | None] = mapped_column(String(500))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    repeat_interval_minutes: Mapped[int | None] = mapped_column()
    reminder_days_before: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdoptionListing(Base):
    __tablename__ = "adoption_listings"
    __table_args__ = (
        CheckConstraint("status IN ('available', 'pending', 'adopted', 'withdrawn')", name="ck_adoption_listings_status"),
        Index("ix_adoption_listings_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shelter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_name: Mapped[str] = mapped_column(String(80), nullable=False)
    species: Mapped[str] = mapped_column(String(40), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_area: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="available", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MissingPetReport(Base):
    __tablename__ = "missing_pet_reports"
    __table_args__ = (
        CheckConstraint("status IN ('missing', 'found', 'closed')", name="ck_missing_pet_reports_status"),
        Index("ix_missing_pet_reports_status_created", "status", "created_at"),
        Index("ix_missing_pet_reports_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_id: Mapped[int | None] = mapped_column(ForeignKey("pets.id", ondelete="SET NULL"))
    pet_name: Mapped[str] = mapped_column(String(80), nullable=False)
    species: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_area: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_instructions: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="missing", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PetSighting(Base):
    __tablename__ = "pet_sightings"
    __table_args__ = (Index("ix_pet_sightings_report_created", "report_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("missing_pet_reports.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    service_area: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
