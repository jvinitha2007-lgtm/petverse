from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, EmergencyDecline, EmergencyRequest, Notification, Pet, User, VolunteerProfile
from app.schemas import (
    EmergencyRequestCreate,
    EmergencyRequestOut,
    EmergencyStatusUpdate,
    NotificationOut,
    VolunteerProfileOut,
    VolunteerProfileUpdate,
)

router = APIRouter(prefix="/api/v1")
ACTIVE_STATUSES = ("submitted", "assigned", "responding", "in_progress")


def add_notification(
    db: Session, *, user_id: int, emergency_id: int, kind: str, message: str, state: str
) -> None:
    db.add(Notification(
        user_id=user_id,
        kind=kind,
        message=message[:300],
        emergency_request_id=emergency_id,
        idempotency_key=f"emergency:{emergency_id}:user:{user_id}:status:{state}",
    ))


def audit_transition(db: Session, request: EmergencyRequest, actor: User, state: str) -> None:
    db.add(AuditLog(
        actor_id=actor.id,
        target_user_id=request.owner_id,
        action=f"emergency_{state}",
        details=f"request_id={request.id}",
    ))


def visible_request(request: EmergencyRequest, include_location: bool) -> EmergencyRequestOut:
    result = EmergencyRequestOut.model_validate(request)
    if not include_location:
        result.location = None
    return result


def volunteer_matches_area(profile: VolunteerProfile, request: EmergencyRequest) -> bool:
    return (
        not profile.service_area
        or not request.location
        or profile.service_area.casefold() in request.location.casefold()
    )


@router.put("/volunteers/me/profile", response_model=VolunteerProfileOut)
def update_volunteer_profile(
    payload: VolunteerProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VolunteerProfile:
    if user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Verified volunteer access is required")
    profile = db.scalar(select(VolunteerProfile).where(VolunteerProfile.user_id == user.id))
    if profile is None:
        profile = VolunteerProfile(user_id=user.id, **payload.model_dump())
        db.add(profile)
    else:
        profile.service_area = payload.service_area
        profile.is_available = payload.is_available
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/volunteers/me/profile", response_model=VolunteerProfileOut)
def get_volunteer_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VolunteerProfile:
    if user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Verified volunteer access is required")
    profile = db.scalar(select(VolunteerProfile).where(VolunteerProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Set your volunteer area and availability to get started")
    return profile


@router.post("/emergencies", response_model=EmergencyRequestOut, status_code=status.HTTP_201_CREATED)
def create_emergency_request(
    payload: EmergencyRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmergencyRequest:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only pet owners can submit assistance requests")
    if payload.pet_id is not None:
        pet = db.scalar(select(Pet).where(
            Pet.id == payload.pet_id,
            Pet.owner_id == user.id,
            Pet.archived.is_(False),
        ))
        if pet is None:
            raise HTTPException(status_code=404, detail="Pet not found")
    request = EmergencyRequest(
        owner_id=user.id,
        pet_id=payload.pet_id,
        category=payload.category,
        severity=payload.severity,
        description=payload.description.strip(),
        location=payload.location,
    )
    db.add(request)
    db.flush()
    add_notification(
        db,
        user_id=user.id,
        emergency_id=request.id,
        kind="emergency",
        message="Your assistance request was submitted. Contact an emergency veterinarian directly for urgent care.",
        state="submitted",
    )
    audit_transition(db, request, user, "submitted")
    db.commit()
    db.refresh(request)
    return request


@router.get("/emergencies/mine", response_model=list[EmergencyRequestOut])
def list_my_emergency_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EmergencyRequestOut]:
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Use the volunteer request queue for assigned assistance")
    query = select(EmergencyRequest)
    if user.role == "owner":
        query = query.where(EmergencyRequest.owner_id == user.id)
    requests = db.scalars(query.order_by(EmergencyRequest.created_at.desc()).offset(offset).limit(limit))
    return [visible_request(request, True) for request in requests]


@router.get("/emergencies/available", response_model=list[EmergencyRequestOut])
def list_available_emergency_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EmergencyRequestOut]:
    if user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Verified volunteer access is required")
    profile = db.scalar(select(VolunteerProfile).where(VolunteerProfile.user_id == user.id))
    if profile is None:
        return []
    assigned = (
        (EmergencyRequest.assigned_volunteer_id == user.id)
        & EmergencyRequest.status.in_(ACTIVE_STATUSES)
    )
    if profile.is_available:
        unassigned = (
            (EmergencyRequest.status == "submitted")
            & EmergencyRequest.assigned_volunteer_id.is_(None)
        )
        if profile.service_area:
            unassigned = unassigned & (
                EmergencyRequest.location.is_(None)
                | EmergencyRequest.location.ilike(f"%{profile.service_area}%")
            )
        unassigned = unassigned & ~select(EmergencyDecline.id).where(
            EmergencyDecline.emergency_request_id == EmergencyRequest.id,
            EmergencyDecline.volunteer_user_id == user.id,
        ).exists()
        visible = unassigned | assigned
    else:
        visible = assigned
    query = select(EmergencyRequest).where(visible)
    requests = db.scalars(
        query.order_by(
            case((EmergencyRequest.severity == "critical", 0), else_=1),
            EmergencyRequest.created_at,
        )
        .offset(offset).limit(limit)
    )
    return [visible_request(request, request.assigned_volunteer_id == user.id) for request in requests]


@router.get("/emergencies/{request_id}", response_model=EmergencyRequestOut)
def get_emergency_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmergencyRequestOut:
    request = db.get(EmergencyRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Assistance request not found")
    if user.role == "admin" or request.owner_id == user.id:
        return visible_request(request, True)
    if request.assigned_volunteer_id == user.id and user.role == "volunteer":
        return visible_request(request, True)
    if user.role == "volunteer" and request.status == "submitted":
        profile = db.scalar(select(VolunteerProfile).where(
            VolunteerProfile.user_id == user.id,
            VolunteerProfile.is_available.is_(True),
        ))
        if profile is None or not volunteer_matches_area(profile, request):
            raise HTTPException(status_code=404, detail="Assistance request not found")
        return visible_request(request, False)
    raise HTTPException(status_code=404, detail="Assistance request not found")


@router.post("/emergencies/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_emergency_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Verified volunteer access is required")
    profile = db.scalar(select(VolunteerProfile).where(
        VolunteerProfile.user_id == user.id,
        VolunteerProfile.is_available.is_(True),
    ))
    request = db.get(EmergencyRequest, request_id)
    if (
        profile is None
        or request is None
        or request.status != "submitted"
        or request.assigned_volunteer_id is not None
        or not volunteer_matches_area(profile, request)
    ):
        raise HTTPException(status_code=404, detail="Assistance request not found")
    db.add(EmergencyDecline(emergency_request_id=request.id, volunteer_user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You already declined this request")
    return None


@router.post("/emergencies/{request_id}/accept", response_model=EmergencyRequestOut)
def accept_emergency_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmergencyRequestOut:
    if user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Verified volunteer access is required")
    profile = db.scalar(
        select(VolunteerProfile).where(
            VolunteerProfile.user_id == user.id,
            VolunteerProfile.is_available.is_(True),
        ).with_for_update()
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Set yourself as available before accepting a request")
    open_request = db.get(EmergencyRequest, request_id)
    if (
        open_request is None
        or open_request.status != "submitted"
        or open_request.assigned_volunteer_id is not None
    ):
        raise HTTPException(status_code=409, detail="This request has already been assigned or is no longer available")
    if not volunteer_matches_area(profile, open_request):
        raise HTTPException(status_code=404, detail="Assistance request not found")
    active_assignment = db.scalar(select(EmergencyRequest.id).where(
        EmergencyRequest.assigned_volunteer_id == user.id,
        EmergencyRequest.status.in_(ACTIVE_STATUSES),
    ).limit(1))
    if active_assignment is not None:
        raise HTTPException(status_code=409, detail="Complete or escalate your active request before accepting another")

    query = update(EmergencyRequest).where(
        EmergencyRequest.id == request_id,
        EmergencyRequest.status == "submitted",
        EmergencyRequest.assigned_volunteer_id.is_(None),
    ).values(
        assigned_volunteer_id=user.id,
        status="assigned",
        updated_at=datetime.now(timezone.utc),
    )
    try:
        result = db.execute(query)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You already have an active assistance assignment")
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This request has already been assigned or is no longer available")
    profile.is_available = False
    request = db.get(EmergencyRequest, request_id)
    if request is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Assistance request not found")
    add_notification(
        db,
        user_id=request.owner_id,
        emergency_id=request.id,
        kind="emergency",
        message="A verified volunteer accepted your assistance request.",
        state="assigned",
    )
    add_notification(
        db,
        user_id=user.id,
        emergency_id=request.id,
        kind="emergency",
        message=f"You accepted assistance request #{request.id}.",
        state="assigned",
    )
    audit_transition(db, request, user, "assigned")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This request or volunteer assignment changed concurrently")
    db.refresh(request)
    return visible_request(request, True)


@router.patch("/emergencies/{request_id}/status", response_model=EmergencyRequestOut)
def update_emergency_status(
    request_id: int,
    payload: EmergencyStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmergencyRequestOut:
    request = db.scalar(select(EmergencyRequest).where(
        EmergencyRequest.id == request_id,
    ).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail="Assistance request not found")

    if user.role == "owner" and request.owner_id == user.id:
        if payload.status not in ("cancelled", "escalated") or request.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=403, detail="Owners may cancel or escalate an active request")
    elif user.role == "volunteer" and request.assigned_volunteer_id == user.id:
        allowed = {
            "assigned": {"responding", "in_progress", "escalated"},
            "responding": {"in_progress", "completed", "escalated"},
            "in_progress": {"completed", "escalated"},
        }
        if payload.status not in allowed.get(request.status, set()):
            raise HTTPException(status_code=409, detail="This request cannot transition to that status")
    elif user.role == "admin":
        if request.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail="This request is already closed")
        if payload.status not in ("completed", "cancelled", "escalated"):
            raise HTTPException(status_code=409, detail="Administrators may close or escalate an active request")
    else:
        raise HTTPException(status_code=404, detail="Assistance request not found")

    request.status = payload.status
    request.updated_at = datetime.now(timezone.utc)
    if payload.status in ("cancelled", "completed", "escalated") and request.assigned_volunteer_id:
        volunteer = db.scalar(
            select(VolunteerProfile).where(VolunteerProfile.user_id == request.assigned_volunteer_id)
        )
        if volunteer and payload.status in ("completed", "cancelled", "escalated"):
            volunteer.is_available = True
    add_notification(
        db,
        user_id=request.owner_id,
        emergency_id=request.id,
        kind="emergency",
        message=f"Your assistance request status is now {payload.status.replace('_', ' ')}.",
        state=payload.status,
    )
    if request.assigned_volunteer_id and request.assigned_volunteer_id != user.id:
        add_notification(
            db,
            user_id=request.assigned_volunteer_id,
            emergency_id=request.id,
            kind="emergency",
            message=f"Assistance request #{request.id} status is now {payload.status.replace('_', ' ')}.",
            state=payload.status,
        )
    audit_transition(db, request, user, payload.status)
    db.commit()
    db.refresh(request)
    return visible_request(request, True)


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Notification]:
    return list(db.scalars(
        select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    ))


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Notification:
    notification = db.scalar(select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ))
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
