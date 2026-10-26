from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import (
    Appointment,
    Conversation,
    ConversationParticipant,
    EmergencyRequest,
    Message,
    Notification,
    ProviderProfile,
    User,
)
from app.schemas import ConversationCreate, ConversationOut, MessageCreate, MessageOut

router = APIRouter(prefix="/api/v1")


def context_participants(
    db: Session, context_type: str, context_id: int, user: User
) -> tuple[int | None, int | None, list[int]]:
    if context_type == "appointment":
        appointment = db.get(Appointment, context_id)
        if appointment is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        profile = db.get(ProviderProfile, appointment.provider_id)
        if profile is None or user.id not in (appointment.owner_id, profile.user_id):
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.status in ("cancelled", "rejected"):
            raise HTTPException(status_code=409, detail="Messaging is unavailable for this appointment")
        return appointment.id, None, [appointment.owner_id, profile.user_id]

    emergency = db.get(EmergencyRequest, context_id)
    if (
        emergency is None
        or emergency.assigned_volunteer_id is None
        or user.id not in (emergency.owner_id, emergency.assigned_volunteer_id)
    ):
        raise HTTPException(status_code=404, detail="Assigned assistance request not found")
    return None, emergency.id, [emergency.owner_id, emergency.assigned_volunteer_id]


def require_participant(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(Conversation.id == conversation_id, ConversationParticipant.user_id == user_id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def serialize_conversation(db: Session, conversation: Conversation, user_id: int) -> ConversationOut:
    other_user = db.scalar(
        select(User)
        .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
        .where(
            ConversationParticipant.conversation_id == conversation.id,
            User.id != user_id,
        )
    )
    if other_user is None:
        raise HTTPException(status_code=500, detail="Conversation participant data is incomplete")
    last_message = db.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    unread_count = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.sender_id != user_id,
            Message.read_at.is_(None),
        )
    ) or 0
    return ConversationOut(
        id=conversation.id,
        appointment_id=conversation.appointment_id,
        emergency_request_id=conversation.emergency_request_id,
        other_user_id=other_user.id,
        other_user_name=other_user.full_name,
        last_message=last_message.body[:180] if last_message else None,
        last_message_at=last_message.created_at if last_message else None,
        unread_count=unread_count,
        updated_at=conversation.updated_at,
    )


def serialize_message(db: Session, message: Message) -> MessageOut:
    sender = db.get(User, message.sender_id)
    if sender is None:
        raise HTTPException(status_code=500, detail="Message sender no longer exists")
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=sender.full_name,
        body=message.body,
        created_at=message.created_at,
        read_at=message.read_at,
    )


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_200_OK)
def open_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationOut:
    appointment_id, emergency_id, participant_ids = context_participants(
        db, payload.context_type, payload.context_id, user
    )
    if appointment_id is not None:
        conversation = db.scalar(
            select(Conversation).where(Conversation.appointment_id == appointment_id)
        )
    else:
        conversation = db.scalar(
            select(Conversation).where(Conversation.emergency_request_id == emergency_id)
        )
    if conversation is None:
        conversation = Conversation(
            appointment_id=appointment_id,
            emergency_request_id=emergency_id,
        )
        db.add(conversation)
        try:
            db.flush()
            db.add_all([
                ConversationParticipant(conversation_id=conversation.id, user_id=participant_id)
                for participant_id in participant_ids
            ])
            db.commit()
        except IntegrityError:
            db.rollback()
            if appointment_id is not None:
                conversation = db.scalar(
                    select(Conversation).where(Conversation.appointment_id == appointment_id)
                )
            else:
                conversation = db.scalar(
                    select(Conversation).where(Conversation.emergency_request_id == emergency_id)
                )
            if conversation is None:
                raise HTTPException(status_code=409, detail="Unable to open this conversation")
        else:
            db.refresh(conversation)
    else:
        db.commit()
    return serialize_conversation(db, conversation, user.id)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    conversations = db.scalars(
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(ConversationParticipant.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [serialize_conversation(db, conversation, user.id) for conversation in conversations]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: int,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    require_participant(db, conversation_id, user.id)
    db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user.id,
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    messages = list(db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .offset(offset)
        .limit(limit)
    ))
    messages.reverse()
    return [serialize_message(db, message) for message in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    conversation = require_participant(db, conversation_id, user.id)
    recipient = db.scalar(
        select(User)
        .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            User.id != user.id,
            User.is_suspended.is_(False),
        )
    )
    if recipient is None:
        raise HTTPException(status_code=409, detail="Conversation recipient is unavailable")
    message = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        body=payload.body,
    )
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(message)
    db.flush()
    db.add(Notification(
        user_id=recipient.id,
        kind="message",
        message=f"New message from {user.full_name}"[:300],
        idempotency_key=f"message:{message.id}:recipient:{recipient.id}",
    ))
    db.commit()
    db.refresh(message)
    return serialize_message(db, message)
