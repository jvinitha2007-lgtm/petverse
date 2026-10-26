from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.dependencies import get_current_user, require_admin
from app.models import (
    Appointment,
    AuthToken,
    AuditLog,
    CareTask,
    EmergencyRequest,
    MedicalRecord,
    Pet,
    ProfessionalApplication,
    ProviderAvailability,
    ProviderProfile,
    User,
)
from app.schemas import (
    AuthMessageOut,
    AuthTokenRequest,
    AdminUserOut,
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
    AppointmentReview,
    AvailabilityCreate,
    AvailabilityOut,
    CareTaskCreate,
    CareTaskOut,
    DashboardOut,
    EmailActionRequest,
    LoginRequest,
    MedicalRecordCreate,
    MedicalRecordOut,
    PetCreate,
    PetOut,
    PetUpdate,
    ProviderProfileCreate,
    ProviderProfileOut,
    ProfessionalApplicationCreate,
    ProfessionalApplicationOut,
    ProfessionalApplicationReview,
    PasswordResetRequest,
    TokenOut,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/api/v1")


def deliver_auth_link(db: Session, user: User, purpose: str) -> None:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.add(AuthToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=now + timedelta(minutes=30),
    ))
    db.commit()

    action = "verify" if purpose == "email_verification" else "reset"
    link = f"{settings.frontend_url.rstrip('/')}/?{action}={quote(raw_token)}"
    subject = "Verify your PetVerse email" if purpose == "email_verification" else "Reset your PetVerse password"
    instruction = "Verify your email address" if purpose == "email_verification" else "Choose a new password"
    email_service.send_email(
        user.email,
        subject,
        f"{instruction} using this one-time link within 30 minutes:\n\n{link}\n\n"
        "If you did not request this, you can ignore this email.",
    )


def lookup_auth_token(db: Session, raw_token: str, purpose: str) -> tuple[AuthToken, User]:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    record = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > datetime.now(timezone.utc),
        )
    )
    if record is None:
        raise HTTPException(status_code=400, detail="This link is invalid or expired")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="This link is invalid or expired")
    return record, user


@router.post("/auth/register", response_model=AuthMessageOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> AuthMessageOut:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Unable to create account with those details")
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        deliver_auth_link(db, user, "email_verification")
    except email_service.EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail="Email delivery is unavailable. Please try again later.") from exc
    return AuthMessageOut(message="Check your email for a verification link before signing in.")


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or user.is_suspended or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email address before signing in")
    return TokenOut(access_token=create_access_token(str(user.id)), user=user)


@router.post("/auth/verify-email", response_model=AuthMessageOut)
def verify_email(payload: AuthTokenRequest, db: Session = Depends(get_db)) -> AuthMessageOut:
    record, user = lookup_auth_token(db, payload.token, "email_verification")
    now = datetime.now(timezone.utc)
    consumed = db.execute(
        update(AuthToken)
        .where(
            AuthToken.id == record.id,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="This link is invalid or expired")
    user.email_verified = True
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == "email_verification", AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    return AuthMessageOut(message="Email verified. You can now sign in.")


@router.post("/auth/resend-verification", response_model=AuthMessageOut)
def resend_verification(
    payload: EmailActionRequest,
    db: Session = Depends(get_db),
) -> AuthMessageOut:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is not None and not user.email_verified:
        try:
            deliver_auth_link(db, user, "email_verification")
        except email_service.EmailDeliveryError as exc:
            raise HTTPException(
                status_code=503,
                detail="Email delivery is unavailable. Please try again later.",
            ) from exc
    return AuthMessageOut(message="If the account needs verification, a link will be sent to its email address.")


@router.post("/auth/password-reset/request", response_model=AuthMessageOut)
def request_password_reset(
    payload: EmailActionRequest,
    db: Session = Depends(get_db),
) -> AuthMessageOut:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is not None and not user.is_suspended:
        try:
            deliver_auth_link(db, user, "password_reset")
        except email_service.EmailDeliveryError as exc:
            raise HTTPException(
                status_code=503,
                detail="Email delivery is unavailable. Please try again later.",
            ) from exc
    return AuthMessageOut(message="If an eligible account exists, a password reset link will be sent.")


@router.post("/auth/password-reset/confirm", response_model=AuthMessageOut)
def confirm_password_reset(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> AuthMessageOut:
    record, user = lookup_auth_token(db, payload.token, "password_reset")
    now = datetime.now(timezone.utc)
    consumed = db.execute(
        update(AuthToken)
        .where(
            AuthToken.id == record.id,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="This link is invalid or expired")
    user.password_hash = hash_password(payload.password)
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    return AuthMessageOut(message="Password reset. You can now sign in with your new password.")


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


def owned_pet(db: Session, user_id: int, pet_id: int) -> Pet:
    pet = db.scalar(select(Pet).where(Pet.id == pet_id, Pet.owner_id == user_id, Pet.archived.is_(False)))
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


@router.get("/pets", response_model=list[PetOut])
def list_pets(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Pet]:
    return list(db.scalars(
        select(Pet).where(Pet.owner_id == user.id, Pet.archived.is_(False))
        .order_by(Pet.created_at.desc()).offset(offset).limit(limit)
    ))


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
def create_pet(payload: PetCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Pet:
    pet = Pet(owner_id=user.id, **payload.model_dump())
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.patch("/pets/{pet_id}", response_model=PetOut)
def update_pet(
    pet_id: int, payload: PetUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Pet:
    pet = owned_pet(db, user.id, pet_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(pet, key, value)
    db.commit()
    db.refresh(pet)
    return pet


@router.delete("/pets/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_pet(pet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    pet = owned_pet(db, user.id, pet_id)
    pet.archived = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pets/{pet_id}/records", response_model=list[MedicalRecordOut])
def list_records(
    pet_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MedicalRecord]:
    owned_pet(db, user.id, pet_id)
    return list(db.scalars(
        select(MedicalRecord).where(MedicalRecord.pet_id == pet_id)
        .order_by(MedicalRecord.recorded_at.desc()).offset(offset).limit(limit)
    ))


@router.post("/pets/{pet_id}/records", response_model=MedicalRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(
    pet_id: int,
    payload: MedicalRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MedicalRecord:
    owned_pet(db, user.id, pet_id)
    record = MedicalRecord(
        pet_id=pet_id,
        **payload.model_dump(exclude={"recorded_at"}),
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
        professional_record=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/care-tasks", response_model=list[CareTaskOut])
def list_care_tasks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CareTask]:
    return list(db.scalars(
        select(CareTask).join(Pet).where(Pet.owner_id == user.id, Pet.archived.is_(False))
        .order_by(CareTask.due_at).offset(offset).limit(limit)
    ))


@router.post("/care-tasks", response_model=CareTaskOut, status_code=status.HTTP_201_CREATED)
def create_care_task(
    payload: CareTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CareTask:
    owned_pet(db, user.id, payload.pet_id)
    task = CareTask(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/care-tasks/{task_id}/complete", response_model=CareTaskOut)
def complete_care_task(
    task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CareTask:
    task = db.scalar(
        select(CareTask).join(Pet).where(CareTask.id == task_id, Pet.owner_id == user.id, Pet.archived.is_(False))
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Care task not found")
    if task.completed:
        raise HTTPException(status_code=409, detail="This care task is already complete")
    now = datetime.now(timezone.utc)
    task.completed = True
    if task.repeat_interval_minutes is not None:
        next_due = task.due_at
        if next_due.tzinfo is None:
            next_due = next_due.replace(tzinfo=timezone.utc)
        interval = timedelta(minutes=task.repeat_interval_minutes)
        next_due += interval
        while next_due <= now:
            next_due += interval
        db.add(CareTask(
            pet_id=task.pet_id,
            title=task.title,
            category=task.category,
            instructions=task.instructions,
            due_at=next_due,
            repeat_interval_minutes=task.repeat_interval_minutes,
            reminder_days_before=task.reminder_days_before,
        ))
    db.commit()
    db.refresh(task)
    return task


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardOut:
    if user.role in ("veterinarian", "groomer"):
        profile_id = db.scalar(select(ProviderProfile.id).where(ProviderProfile.user_id == user.id))
        pending = db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.provider_id == profile_id,
                Appointment.status == "pending",
            )
        ) or 0
        active = db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.provider_id == profile_id,
                Appointment.status.in_(("pending", "confirmed")),
            )
        ) or 0
        return DashboardOut(
            role=user.role,
            pet_count=0,
            due_tasks=0,
            completed_tasks=0,
            recent_records=0,
            upcoming_tasks=[],
            pending_appointments=pending,
            active_appointments=active,
        )
    if user.role == "volunteer":
        active = db.scalar(
            select(func.count()).select_from(EmergencyRequest).where(
                EmergencyRequest.assigned_volunteer_id == user.id,
                EmergencyRequest.status.in_(("assigned", "responding", "in_progress")),
            )
        ) or 0
        return DashboardOut(
            role=user.role,
            pet_count=0,
            due_tasks=0,
            completed_tasks=0,
            recent_records=0,
            upcoming_tasks=[],
            active_emergencies=active,
        )
    if user.role == "admin":
        pending = db.scalar(
            select(func.count()).select_from(ProfessionalApplication).where(
                ProfessionalApplication.status == "pending",
            )
        ) or 0
        suspended = db.scalar(
            select(func.count()).select_from(User).where(User.is_suspended.is_(True))
        ) or 0
        return DashboardOut(
            role=user.role,
            pet_count=0,
            due_tasks=0,
            completed_tasks=0,
            recent_records=0,
            upcoming_tasks=[],
            pending_applications=pending,
            suspended_users=suspended,
        )

    pet_ids = select(Pet.id).where(Pet.owner_id == user.id, Pet.archived.is_(False))
    pet_count = db.scalar(select(func.count()).select_from(Pet).where(Pet.owner_id == user.id, Pet.archived.is_(False))) or 0
    due_tasks = db.scalar(
        select(func.count()).select_from(CareTask).where(CareTask.pet_id.in_(pet_ids), CareTask.completed.is_(False))
    ) or 0
    completed_tasks = db.scalar(
        select(func.count()).select_from(CareTask).where(CareTask.pet_id.in_(pet_ids), CareTask.completed.is_(True))
    ) or 0
    recent_records = db.scalar(
        select(func.count()).select_from(MedicalRecord).join(Pet).where(Pet.owner_id == user.id, Pet.archived.is_(False))
    ) or 0
    upcoming = list(db.scalars(
        select(CareTask).where(CareTask.pet_id.in_(pet_ids), CareTask.completed.is_(False))
        .order_by(CareTask.due_at).limit(5)
    ))
    return DashboardOut(
        role=user.role,
        pet_count=pet_count,
        due_tasks=due_tasks,
        completed_tasks=completed_tasks,
        recent_records=recent_records,
        upcoming_tasks=upcoming,
    )


@router.post(
    "/professional-applications",
    response_model=ProfessionalApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_professional_application(
    payload: ProfessionalApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfessionalApplication:
    if user.role != "owner":
        raise HTTPException(status_code=409, detail="This account already has a professional role")
    pending = db.scalar(
        select(ProfessionalApplication.id).where(
            ProfessionalApplication.user_id == user.id,
            ProfessionalApplication.status == "pending",
        )
    )
    if pending is not None:
        raise HTTPException(status_code=409, detail="You already have a pending verification request")
    application = ProfessionalApplication(user_id=user.id, **payload.model_dump())
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A verification request is already pending")
    db.refresh(application)
    return application


@router.get("/professional-applications/me", response_model=list[ProfessionalApplicationOut])
def list_my_professional_applications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProfessionalApplication]:
    return list(db.scalars(
        select(ProfessionalApplication).where(ProfessionalApplication.user_id == user.id)
        .order_by(ProfessionalApplication.created_at.desc())
    ))


@router.get("/admin/professional-applications", response_model=list[ProfessionalApplicationOut])
def list_professional_applications(
    application_status: str = Query(default="pending", alias="status", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ProfessionalApplication]:
    query = select(ProfessionalApplication)
    if application_status != "all":
        query = query.where(ProfessionalApplication.status == application_status)
    return list(db.scalars(query.order_by(ProfessionalApplication.created_at).offset(offset).limit(limit)))


@router.post(
    "/admin/professional-applications/{application_id}/review",
    response_model=ProfessionalApplicationOut,
)
def review_professional_application(
    application_id: int,
    payload: ProfessionalApplicationReview,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProfessionalApplication:
    application = db.scalar(
        select(ProfessionalApplication).where(
            ProfessionalApplication.id == application_id,
            ProfessionalApplication.status == "pending",
        ).with_for_update()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Pending application not found")
    applicant = db.scalar(select(User).where(User.id == application.user_id).with_for_update())
    if applicant is None:
        raise HTTPException(status_code=404, detail="Applicant account not found")
    if payload.decision == "approved" and (applicant.role != "owner" or applicant.is_suspended):
        raise HTTPException(status_code=409, detail="Applicant no longer has an owner account")
    now = datetime.now(timezone.utc)
    application.status = payload.decision
    application.review_notes = payload.review_notes.strip() or None if payload.review_notes else None
    application.reviewed_by = admin.id
    application.reviewed_at = now
    if payload.decision == "approved":
        applicant.role = application.requested_role
    db.add(AuditLog(
        actor_id=admin.id,
        target_user_id=applicant.id,
        action=f"professional_application_{payload.decision}",
        details=f"application_id={application.id};role={application.requested_role}",
    ))
    db.commit()
    db.refresh(application)
    return application


@router.get("/admin/users", response_model=list[AdminUserOut])
def list_users(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)))


@router.patch("/admin/users/{user_id}/suspension", response_model=AdminUserOut)
def set_user_suspension(
    user_id: int,
    suspended: bool = Query(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and suspended:
        raise HTTPException(status_code=400, detail="You cannot suspend your own administrator account")
    if target.role == "admin" and suspended:
        raise HTTPException(status_code=403, detail="Administrator accounts cannot be suspended here")
    target.is_suspended = suspended
    db.add(AuditLog(
        actor_id=admin.id,
        target_user_id=target.id,
        action="account_suspended" if suspended else "account_reinstated",
    ))
    db.commit()
    db.refresh(target)
    return target


@router.get("/admin/audit-logs", response_model=list[dict[str, object]])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict[str, object]]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit))
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "target_user_id": row.target_user_id,
            "action": row.action,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.put("/providers/me/profile", response_model=ProviderProfileOut)
def save_provider_profile(
    payload: ProviderProfileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProviderProfile:
    if user.role not in ("veterinarian", "groomer"):
        raise HTTPException(status_code=403, detail="Verified veterinarian or groomer access is required")
    profile = db.scalar(select(ProviderProfile).where(ProviderProfile.user_id == user.id))
    if profile is None:
        profile = ProviderProfile(user_id=user.id, kind=user.role, **payload.model_dump())
        db.add(profile)
    else:
        profile.kind = user.role
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/providers/me/profile", response_model=ProviderProfileOut)
def get_provider_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProviderProfile:
    if user.role not in ("veterinarian", "groomer"):
        raise HTTPException(status_code=403, detail="Verified provider access is required")
    profile = db.scalar(select(ProviderProfile).where(ProviderProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Create your provider profile to get started")
    return profile


@router.get("/providers", response_model=list[ProviderProfileOut])
def find_providers(
    kind: str | None = Query(default=None, pattern="^(veterinarian|groomer)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ProviderProfile]:
    query = (
        select(ProviderProfile)
        .join(User, User.id == ProviderProfile.user_id)
        .where(User.role == ProviderProfile.kind, User.is_suspended.is_(False))
    )
    if kind:
        query = query.where(ProviderProfile.kind == kind)
    return list(db.scalars(query.order_by(ProviderProfile.display_name).offset(offset).limit(limit)))


@router.post("/providers/me/availability", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED)
def add_provider_availability(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProviderAvailability:
    if user.role not in ("veterinarian", "groomer"):
        raise HTTPException(status_code=403, detail="Verified provider access is required")
    starts_at = payload.starts_at.astimezone(timezone.utc)
    ends_at = payload.ends_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if starts_at <= now or ends_at <= starts_at:
        raise HTTPException(status_code=422, detail="Availability must be a future time range")
    profile = db.scalar(
        select(ProviderProfile).where(ProviderProfile.user_id == user.id).with_for_update()
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your provider profile before adding availability")
    overlap = db.scalar(
        select(ProviderAvailability.id).where(
            ProviderAvailability.provider_id == profile.id,
            ProviderAvailability.starts_at < ends_at,
            ProviderAvailability.ends_at > starts_at,
        ).limit(1)
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="This time overlaps existing provider availability")
    slot = ProviderAvailability(provider_id=profile.id, starts_at=starts_at, ends_at=ends_at)
    db.add(slot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This provider already has an overlapping slot")
    db.refresh(slot)
    return slot


@router.get("/providers/{provider_id}/availability", response_model=list[AvailabilityOut])
def list_provider_availability(
    provider_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ProviderAvailability]:
    provider = db.scalar(
        select(ProviderProfile)
        .join(User, User.id == ProviderProfile.user_id)
        .where(
            ProviderProfile.id == provider_id,
            User.role == ProviderProfile.kind,
            User.is_suspended.is_(False),
        )
    )
    if provider is None:
        raise HTTPException(status_code=404, detail="Verified provider not found")
    return list(db.scalars(
        select(ProviderAvailability)
        .where(
            ProviderAvailability.provider_id == provider_id,
            ProviderAvailability.is_available.is_(True),
            ProviderAvailability.starts_at > datetime.now(timezone.utc),
        )
        .order_by(ProviderAvailability.starts_at).offset(offset).limit(limit)
    ))


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Appointment:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only pet owners can book appointments")
    owned_pet(db, user.id, payload.pet_id)
    slot = db.scalar(
        select(ProviderAvailability)
        .join(ProviderProfile, ProviderProfile.id == ProviderAvailability.provider_id)
        .join(User, User.id == ProviderProfile.user_id)
        .where(
            ProviderAvailability.id == payload.availability_id,
            ProviderAvailability.is_available.is_(True),
            ProviderAvailability.starts_at > datetime.now(timezone.utc),
            User.role == ProviderProfile.kind,
            User.is_suspended.is_(False),
        )
        .with_for_update()
    )
    if slot is None:
        raise HTTPException(status_code=409, detail="This appointment slot is unavailable")
    profile = db.get(ProviderProfile, slot.provider_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Provider profile is unavailable")
    slot.is_available = False
    appointment = Appointment(
        owner_id=user.id,
        pet_id=payload.pet_id,
        provider_id=profile.id,
        availability_id=slot.id,
        service_kind=profile.kind,
        owner_note=payload.owner_note.strip() if payload.owner_note else None,
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This appointment slot was just booked")
    db.refresh(appointment)
    return appointment


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Appointment]:
    query = select(Appointment)
    if user.role == "owner":
        query = query.where(Appointment.owner_id == user.id)
    elif user.role in ("veterinarian", "groomer"):
        profile = db.scalar(select(ProviderProfile).where(ProviderProfile.user_id == user.id))
        if profile is None:
            return []
        query = query.where(Appointment.provider_id == profile.id)
    elif user.role != "admin":
        raise HTTPException(status_code=403, detail="Appointment access is not available for this role")
    return list(db.scalars(
        query.order_by(Appointment.created_at.desc()).offset(offset).limit(limit)
    ))


@router.patch("/appointments/{appointment_id}/status", response_model=AppointmentOut)
def update_appointment_status(
    appointment_id: int,
    payload: AppointmentReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Appointment:
    appointment = db.scalar(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if user.role == "owner" and appointment.owner_id == user.id:
        if payload.status != "cancelled" or appointment.status not in ("pending", "confirmed"):
            raise HTTPException(status_code=403, detail="Owners may only cancel pending or confirmed appointments")
    elif user.role in ("veterinarian", "groomer"):
        profile = db.scalar(select(ProviderProfile).where(ProviderProfile.user_id == user.id))
        if profile is None or appointment.provider_id != profile.id:
            raise HTTPException(status_code=404, detail="Appointment not found")
        allowed = (
            {"confirmed", "rejected", "cancelled"} if appointment.status == "pending"
            else {"completed", "cancelled"} if appointment.status == "confirmed"
            else set()
        )
        if payload.status not in allowed:
            raise HTTPException(status_code=409, detail="This appointment cannot transition to that status")
    else:
        raise HTTPException(status_code=403, detail="Appointment access is not available for this role")
    appointment.status = payload.status
    if payload.status in ("cancelled", "rejected"):
        slot = db.get(ProviderAvailability, appointment.availability_id)
        if slot is not None:
            slot.is_available = True
    db.commit()
    db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Appointment:
    appointment = db.scalar(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    )
    if appointment is None or appointment.owner_id != user.id or user.role != "owner":
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=409, detail="This appointment cannot be rescheduled")
    new_slot = db.scalar(
        select(ProviderAvailability)
        .where(
            ProviderAvailability.id == payload.availability_id,
            ProviderAvailability.provider_id == appointment.provider_id,
            ProviderAvailability.is_available.is_(True),
            ProviderAvailability.starts_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )
    if new_slot is None or new_slot.id == appointment.availability_id:
        raise HTTPException(status_code=409, detail="Choose a different available slot with the same provider")
    old_slot = db.get(ProviderAvailability, appointment.availability_id)
    if old_slot is not None:
        old_slot.is_available = True
    new_slot.is_available = False
    appointment.availability_id = new_slot.id
    appointment.status = "pending"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This appointment slot was just booked")
    db.refresh(appointment)
    return appointment
