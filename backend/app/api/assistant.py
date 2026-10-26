import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.dependencies import get_current_user
from app.models import User
from app.schemas import CareAssistantRequest, CareAssistantResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/care-assistant", tags=["care assistant"])

EMERGENCY_TERMS = (
    "can't breathe", "cannot breathe", "difficulty breathing", "trouble breathing",
    "poison", "toxic", "seizure", "unconscious", "severe bleeding", "hit by a car",
    "heatstroke", "heat stroke", "blue gums",
)
EMERGENCY_ANSWER = (
    "This may be an emergency. Contact an emergency veterinarian or animal poison "
    "control service now. Do not wait for online advice, and do not induce vomiting "
    "or give medication unless a veterinarian instructs you."
)
SYSTEM_PROMPT = (
    "You provide concise, general pet-care education, not veterinary diagnosis or treatment. "
    "Never prescribe medication or dosage, recommend home treatment for urgent symptoms, "
    "or claim certainty. For breathing trouble, suspected poisoning, seizures, collapse, "
    "severe bleeding, trauma, or other urgent symptoms, direct the user to an emergency "
    "veterinarian immediately. Encourage veterinary advice for medical questions. "
    "Do not ask for names, addresses, contact details, or other identifying information."
)


@router.post("", response_model=CareAssistantResponse)
def ask_care_assistant(
    payload: CareAssistantRequest,
    _: User = Depends(get_current_user),
) -> CareAssistantResponse:
    question = payload.question
    if any(term in question.casefold() for term in EMERGENCY_TERMS):
        return CareAssistantResponse(answer=EMERGENCY_ANSWER, urgent=True)
    if not settings.ai_api_key:
        raise HTTPException(status_code=503, detail="Care assistant is not configured")
    parsed_url = urlparse(settings.ai_api_base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise HTTPException(status_code=503, detail="Care assistant endpoint must use HTTPS")

    user_message = question
    if payload.pet_species:
        user_message = f"Pet species: {payload.pet_species.strip()}\nQuestion: {question}"
    request_body = json.dumps({
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 350,
    }).encode("utf-8")
    request = Request(
        f"{settings.ai_api_base_url.rstrip('/')}/chat/completions",
        data=request_body,
        headers={
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.ai_timeout_seconds) as response:
            result = json.loads(response.read(65536))
    except (HTTPError, URLError, TimeoutError, OSError):
        logger.exception("Care assistant provider request failed")
        raise HTTPException(status_code=502, detail="Care assistant is temporarily unavailable")
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("Care assistant provider returned invalid JSON")
        raise HTTPException(status_code=502, detail="Care assistant returned an invalid response")

    try:
        answer = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error("Care assistant provider response did not contain a chat answer")
        raise HTTPException(status_code=502, detail="Care assistant returned an invalid response")
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(status_code=502, detail="Care assistant returned an empty response")
    return CareAssistantResponse(answer=answer.strip())
