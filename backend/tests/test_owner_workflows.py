from datetime import datetime, timedelta, timezone
import re
import json

from app.api import assistant as assistant_api
from app.core.config import settings
from app.core.care_reminders import send_due_care_reminders
from app.db import get_db


def create_account(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Pet Owner", "password": "a-long-test-password"
    })
    assert response.status_code == 201
    assert response.json()["message"].startswith("Check your email")
    verification_link = client.app.state.test_email_outbox.pop()["body"]
    token = re.search(r"\?verify=([A-Za-z0-9_-]+)", verification_link).group(1)
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "a-long-test-password",
    })
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_login_and_owner_scoped_pet_records(client):
    owner_headers = create_account(client)
    other_headers = create_account(client, "other@example.com")
    pet_response = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Bruno", "species": "Dog", "breed": "Mixed", "weight_kg": 12.5
    })
    assert pet_response.status_code == 201
    pet_id = pet_response.json()["id"]

    record_response = client.post(f"/api/v1/pets/{pet_id}/records", headers=owner_headers, json={
        "record_type": "observation", "title": "Energy", "details": "Normal today"
    })
    assert record_response.status_code == 201
    assert record_response.json()["professional_record"] is False

    assert client.get(f"/api/v1/pets/{pet_id}/records", headers=other_headers).status_code == 404
    assert client.get("/api/v1/pets", headers=other_headers).json() == []
    assert client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "a-long-test-password"
    }).status_code == 200


def test_care_task_and_dashboard_are_persisted(client):
    headers = create_account(client)
    pet = client.post("/api/v1/pets", headers=headers, json={
        "name": "Miso", "species": "Cat"
    }).json()
    task = client.post("/api/v1/care-tasks", headers=headers, json={
        "pet_id": pet["id"], "title": "Annual checkup", "category": "vet",
        "due_at": "2030-08-01T10:00:00Z"
    })
    assert task.status_code == 201
    dashboard = client.get("/api/v1/dashboard", headers=headers).json()
    assert dashboard["pet_count"] == 1
    assert dashboard["due_tasks"] == 1
    assert dashboard["upcoming_tasks"][0]["title"] == "Annual checkup"

    completed = client.patch(f"/api/v1/care-tasks/{task.json()['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["completed"] is True


def test_recurring_vaccination_schedule_creates_next_occurrence(client):
    headers = create_account(client, "recurring-care@example.com")
    pet = client.post("/api/v1/pets", headers=headers, json={
        "name": "Pip", "species": "Dog",
    }).json()
    due_at = datetime.now(timezone.utc) + timedelta(days=1)
    created = client.post("/api/v1/care-tasks", headers=headers, json={
        "pet_id": pet["id"],
        "title": "Annual booster",
        "category": "vaccination",
        "instructions": "Bring vaccination booklet",
        "due_at": due_at.isoformat(),
        "repeat_interval_minutes": 525600,
        "reminder_days_before": 7,
    })
    assert created.status_code == 201
    task = created.json()
    assert task["repeat_interval_minutes"] == 525600
    completed = client.patch(f"/api/v1/care-tasks/{task['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert client.patch(f"/api/v1/care-tasks/{task['id']}/complete", headers=headers).status_code == 409
    tasks = client.get("/api/v1/care-tasks", headers=headers).json()
    next_task = next(item for item in tasks if item["id"] != task["id"])
    assert next_task["title"] == "Annual booster"
    assert next_task["instructions"] == "Bring vaccination booklet"
    assert next_task["repeat_interval_minutes"] == 525600
    next_due = datetime.fromisoformat(next_task["due_at"])
    if next_due.tzinfo is None:
        next_due = next_due.replace(tzinfo=timezone.utc)
    assert next_due > datetime.now(timezone.utc)


def test_due_care_reminders_are_sent_once_only_to_verified_active_pet_owners(client):
    headers = create_account(client, "care-email@example.com")
    pet = client.post("/api/v1/pets", headers=headers, json={
        "name": "Clover", "species": "Rabbit",
    }).json()
    due_at = datetime.now(timezone.utc) + timedelta(hours=12)
    task = client.post("/api/v1/care-tasks", headers=headers, json={
        "pet_id": pet["id"],
        "title": "Daily medication",
        "category": "medication",
        "instructions": "Give one prescribed dose",
        "due_at": due_at.isoformat(),
        "reminder_days_before": 1,
    })
    assert task.status_code == 201
    outbox_count = len(client.app.state.test_email_outbox)
    db_generator = client.app.dependency_overrides[get_db]()
    db = next(db_generator)
    sent, failed = send_due_care_reminders(db)
    assert (sent, failed) == (1, 0)
    assert len(client.app.state.test_email_outbox) == outbox_count + 1
    message = client.app.state.test_email_outbox[-1]
    assert message["recipient"] == "care-email@example.com"
    assert "Daily medication" in message["body"]
    assert "Clover" in message["body"]
    sent_again, failed_again = send_due_care_reminders(db)
    assert (sent_again, failed_again) == (0, 0)
    db_generator.close()


def test_dashboard_metrics_are_scoped_to_each_account_role(client):
    owner_headers = create_account(client, "dashboard-owner@example.com")
    assert client.get("/api/v1/dashboard", headers=owner_headers).json()["role"] == "owner"

    applicant_headers = create_account(client, "dashboard-applicant@example.com")
    assert client.post("/api/v1/professional-applications", headers=applicant_headers, json={
        "requested_role": "shelter",
        "organization_name": "Community Shelter",
        "credential_summary": "Community animal shelter requesting access to local pet support tools.",
    }).status_code == 201
    admin_headers = create_admin(client)
    admin_dashboard = client.get("/api/v1/dashboard", headers=admin_headers).json()
    assert admin_dashboard["role"] == "admin"
    assert admin_dashboard["pending_applications"] == 1

    provider_headers = approve_role(client, "dashboard-vet@example.com", "veterinarian")
    profile = client.put("/api/v1/providers/me/profile", headers=provider_headers, json={
        "display_name": "Dashboard Veterinary",
        "bio": "Routine veterinary care and wellness visits for local pets.",
    }).json()
    starts = datetime.now(timezone.utc) + timedelta(days=8)
    slot = client.post("/api/v1/providers/me/availability", headers=provider_headers, json={
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(minutes=30)).isoformat(),
    }).json()
    pet = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Pip", "species": "Dog",
    }).json()
    booked = client.post("/api/v1/appointments", headers=owner_headers, json={
        "pet_id": pet["id"], "availability_id": slot["id"],
    })
    assert booked.status_code == 201
    provider_dashboard = client.get("/api/v1/dashboard", headers=provider_headers).json()
    assert provider_dashboard["role"] == profile["kind"] == "veterinarian"
    assert provider_dashboard["pending_appointments"] == 1
    assert provider_dashboard["active_appointments"] == 1

    volunteer_headers = approve_role(client, "dashboard-volunteer@example.com", "volunteer")
    client.put("/api/v1/volunteers/me/profile", headers=volunteer_headers, json={
        "service_area": "Central", "is_available": True,
    })
    emergency = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "injured_stray",
        "severity": "urgent",
        "description": "A stray animal needs help reaching a shelter.",
    }).json()
    assert client.post(
        f"/api/v1/emergencies/{emergency['id']}/accept",
        headers=volunteer_headers,
    ).status_code == 200
    volunteer_dashboard = client.get("/api/v1/dashboard", headers=volunteer_headers).json()
    assert volunteer_dashboard["role"] == "volunteer"
    assert volunteer_dashboard["active_emergencies"] == 1


def test_auth_and_role_assignment_are_not_client_controlled(client):
    assert client.get("/api/v1/pets").status_code == 401
    escalated = client.post("/api/v1/auth/register", json={
        "email": "escalate@example.com", "full_name": "Pet Owner",
        "password": "a-long-test-password", "role": "admin",
    })
    assert escalated.status_code == 422
    headers = create_account(client)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["role"] == "owner"
    assert "password_hash" not in me


def test_duplicate_registration_and_invalid_login_are_rejected(client):
    create_account(client)
    duplicate = client.post("/api/v1/auth/register", json={
        "email": "owner@example.com", "full_name": "Someone Else", "password": "a-long-test-password"
    })
    assert duplicate.status_code == 409
    invalid = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "incorrect-password"
    })
    assert invalid.status_code == 401


def test_email_verification_links_are_single_use_and_required_for_sign_in(client):
    registration = client.post("/api/v1/auth/register", json={
        "email": "verify-me@example.com",
        "full_name": "Needs Verification",
        "password": "a-long-test-password",
    })
    assert registration.status_code == 201
    original_link = client.app.state.test_email_outbox.pop()["body"]
    original_token = re.search(r"\?verify=([A-Za-z0-9_-]+)", original_link).group(1)
    assert client.post("/api/v1/auth/login", json={
        "email": "verify-me@example.com", "password": "a-long-test-password",
    }).status_code == 403
    assert client.post("/api/v1/auth/resend-verification", json={
        "email": "missing@example.com",
    }).json()["message"].startswith("If the account")
    assert client.post("/api/v1/auth/resend-verification", json={
        "email": "verify-me@example.com",
    }).status_code == 200
    refreshed_link = client.app.state.test_email_outbox.pop()["body"]
    refreshed_token = re.search(r"\?verify=([A-Za-z0-9_-]+)", refreshed_link).group(1)
    assert client.post("/api/v1/auth/verify-email", json={"token": original_token}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": refreshed_token}).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json={"token": refreshed_token}).status_code == 400
    assert client.post("/api/v1/auth/login", json={
        "email": "verify-me@example.com", "password": "a-long-test-password",
    }).status_code == 200


def test_password_reset_is_single_use_and_does_not_disclose_unknown_accounts(client):
    create_account(client, "recover@example.com")
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "absent@example.com"})
    known = client.post("/api/v1/auth/password-reset/request", json={"email": "recover@example.com"})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    reset_link = client.app.state.test_email_outbox.pop()["body"]
    token = re.search(r"\?reset=([A-Za-z0-9_-]+)", reset_link).group(1)

    reset = client.post("/api/v1/auth/password-reset/confirm", json={
        "token": token, "password": "a-different-long-password",
    })
    assert reset.status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json={
        "token": token, "password": "another-long-password",
    }).status_code == 400
    assert client.post("/api/v1/auth/login", json={
        "email": "recover@example.com", "password": "a-long-test-password",
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "recover@example.com", "password": "a-different-long-password",
    }).status_code == 200


def create_admin(client):
    login = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": "a-long-test-password",
    })
    if login.status_code == 200:
        return {"Authorization": f"Bearer {login.json()['access_token']}"}
    headers = create_account(client, "admin@example.com")
    from app.db import get_db
    from app.models import User

    db_generator = client.app.dependency_overrides[get_db]()
    db = next(db_generator)
    user = db.query(User).filter_by(email="admin@example.com").one()
    user.role = "admin"
    db.commit()
    db_generator.close()
    return headers


def test_professional_applications_require_admin_review(client):
    owner_headers = create_account(client, "vet@example.com")
    assert client.get("/api/v1/admin/professional-applications", headers=owner_headers).status_code == 403

    application = client.post("/api/v1/professional-applications", headers=owner_headers, json={
        "requested_role": "veterinarian",
        "organization_name": "Northside Animal Clinic",
        "credential_summary": "Licensed veterinarian, state registration number VET-12345",
    })
    assert application.status_code == 201
    assert application.json()["status"] == "pending"
    assert client.get("/api/v1/auth/me", headers=owner_headers).json()["role"] == "owner"
    assert client.post("/api/v1/professional-applications", headers=owner_headers, json={
        "requested_role": "groomer",
        "organization_name": "Grooming",
        "credential_summary": "I have five years of professional grooming experience",
    }).status_code == 409

    admin_headers = create_admin(client)
    queue = client.get("/api/v1/admin/professional-applications", headers=admin_headers)
    assert queue.status_code == 200
    assert queue.json()[0]["id"] == application.json()["id"]
    reviewed = client.post(
        f"/api/v1/admin/professional-applications/{application.json()['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "review_notes": "Credentials checked"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    assert client.get("/api/v1/auth/me", headers=owner_headers).json()["role"] == "veterinarian"
    assert client.post(
        f"/api/v1/admin/professional-applications/{application.json()['id']}/review",
        headers=admin_headers,
        json={"decision": "rejected"},
    ).status_code == 404


def test_admin_suspension_revokes_access_and_audits_change(client):
    owner_headers = create_account(client)
    admin_headers = create_admin(client)
    suspended = client.patch(
        "/api/v1/admin/users/1/suspension?suspended=true",
        headers=admin_headers,
    )
    assert suspended.status_code == 200
    assert suspended.json()["is_suspended"] is True
    assert client.get("/api/v1/auth/me", headers=owner_headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "a-long-test-password"
    }).status_code == 401
    logs = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    assert logs.json()[0]["action"] == "account_suspended"


def approve_role(client, email, role):
    owner_headers = create_account(client, email)
    application = client.post("/api/v1/professional-applications", headers=owner_headers, json={
        "requested_role": role,
        "organization_name": f"{role.title()} practice",
        "credential_summary": "Verified professional credentials submitted for administrator review.",
    })
    assert application.status_code == 201
    admin_headers = create_admin(client)
    review = client.post(
        f"/api/v1/admin/professional-applications/{application.json()['id']}/review",
        headers=admin_headers,
        json={"decision": "approved"},
    )
    assert review.status_code == 200
    return owner_headers


def test_shelter_adoption_listings_require_verified_shelter_and_owner_status(client):
    owner_headers = create_account(client, "adoption-owner@example.com")
    listing_payload = {
        "pet_name": "Maple",
        "species": "Cat",
        "breed": "Tabby",
        "description": "Gentle adult cat looking for a calm indoor home.",
        "service_area": "Northside",
    }
    assert client.post("/api/v1/adoptions", headers=owner_headers, json=listing_payload).status_code == 403
    shelter_headers = approve_role(client, "adoption-shelter@example.com", "shelter")
    created = client.post("/api/v1/adoptions", headers=shelter_headers, json=listing_payload)
    assert created.status_code == 201
    listing_id = created.json()["id"]
    assert client.get("/api/v1/adoptions", headers=owner_headers).json()[0]["pet_name"] == "Maple"
    assert client.patch(f"/api/v1/adoptions/{listing_id}/status", headers=owner_headers, json={
        "status": "adopted",
    }).status_code == 404
    updated = client.patch(f"/api/v1/adoptions/{listing_id}/status", headers=shelter_headers, json={
        "status": "adopted",
    })
    assert updated.status_code == 200
    assert updated.json()["status"] == "adopted"
    assert client.get("/api/v1/adoptions", headers=owner_headers).json() == []


def test_missing_pet_report_sighting_and_owner_status_permissions(client):
    owner_headers = create_account(client, "missing-owner@example.com")
    stranger_headers = create_account(client, "sighting-helper@example.com")
    pet = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Nori", "species": "Cat",
    }).json()
    forbidden = client.post("/api/v1/missing-pets", headers=stranger_headers, json={
        "pet_id": pet["id"],
        "description": "A cat is missing from its family.",
        "service_area": "West district",
        "contact_instructions": "Use the PetVerse message center.",
    })
    assert forbidden.status_code == 404
    created = client.post("/api/v1/missing-pets", headers=owner_headers, json={
        "pet_id": pet["id"],
        "description": "Small black cat wearing a blue collar.",
        "service_area": "West district",
        "contact_instructions": "Use the PetVerse message center.",
    })
    assert created.status_code == 201
    report = created.json()
    assert report["pet_name"] == "Nori"
    assert report["owner_id"] != stranger_headers.get("user_id")

    sighting = client.post(f"/api/v1/missing-pets/{report['id']}/sightings", headers=stranger_headers, json={
        "description": "Black cat near the library entrance.",
        "service_area": "West district library",
    })
    assert sighting.status_code == 201
    assert len(client.get(
        f"/api/v1/missing-pets/{report['id']}/sightings", headers=owner_headers,
    ).json()) == 1
    assert client.patch(f"/api/v1/missing-pets/{report['id']}/status", headers=stranger_headers, json={
        "status": "found",
    }).status_code == 404
    found = client.patch(f"/api/v1/missing-pets/{report['id']}/status", headers=owner_headers, json={
        "status": "found",
    })
    assert found.status_code == 200
    assert found.json()["status"] == "found"
    assert client.get("/api/v1/missing-pets", headers=stranger_headers).json() == []


def test_care_assistant_requires_auth_and_provider_configuration(client, monkeypatch):
    assert client.post("/api/v1/care-assistant", json={
        "question": "How often should I brush my dog?",
    }).status_code == 401
    headers = create_account(client, "assistant-user@example.com")
    not_configured = client.post("/api/v1/care-assistant", headers=headers, json={
        "question": "How often should I brush my dog?",
    })
    assert not_configured.status_code == 503

    emergency = client.post("/api/v1/care-assistant", headers=headers, json={
        "question": "My dog may have eaten poison",
    })
    assert emergency.status_code == 200
    assert emergency.json()["urgent"] is True
    assert "emergency veterinarian" in emergency.json()["answer"]

    monkeypatch.setattr(settings, "ai_api_key", "test-provider-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _limit):
            return json.dumps({
                "choices": [{"message": {"content": "Brush regularly and ask a veterinarian about coat-specific needs."}}],
            }).encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(assistant_api, "urlopen", fake_urlopen)
    response = client.post("/api/v1/care-assistant", headers=headers, json={
        "question": "How often should I brush my dog?",
        "pet_species": "Dog",
    })
    assert response.status_code == 200
    assert response.json()["urgent"] is False
    assert "Brush regularly" in response.json()["answer"]
    assert captured["request"].get_header("Authorization") == "Bearer test-provider-key"
    request_body = json.loads(captured["request"].data)
    assert request_body["messages"][1]["content"] == "Pet species: Dog\nQuestion: How often should I brush my dog?"
    assert captured["timeout"] == settings.ai_timeout_seconds


def test_veterinary_booking_is_owner_scoped_and_prevents_double_booking(client):
    provider_headers = approve_role(client, "provider@example.com", "veterinarian")
    profile_response = client.put("/api/v1/providers/me/profile", headers=provider_headers, json={
        "display_name": "Northside Veterinary",
        "bio": "Routine and preventative veterinary care for local pets.",
        "service_area": "Northside",
        "service_fee": 60,
    })
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["kind"] == "veterinarian"

    starts = datetime.now(timezone.utc) + timedelta(days=7)
    ends = starts + timedelta(minutes=30)
    slot_response = client.post("/api/v1/providers/me/availability", headers=provider_headers, json={
        "starts_at": starts.isoformat(), "ends_at": ends.isoformat(),
    })
    assert slot_response.status_code == 201
    slot = slot_response.json()
    overlap = client.post("/api/v1/providers/me/availability", headers=provider_headers, json={
        "starts_at": (starts + timedelta(minutes=10)).isoformat(),
        "ends_at": (ends + timedelta(minutes=10)).isoformat(),
    })
    assert overlap.status_code == 409
    later_slot_response = client.post("/api/v1/providers/me/availability", headers=provider_headers, json={
        "starts_at": (starts + timedelta(days=1)).isoformat(),
        "ends_at": (ends + timedelta(days=1)).isoformat(),
    })
    assert later_slot_response.status_code == 201

    owner_headers = create_account(client, "booker@example.com")
    pet = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Pip", "species": "Dog",
    }).json()
    booking = client.post("/api/v1/appointments", headers=owner_headers, json={
        "pet_id": pet["id"], "availability_id": slot["id"], "owner_note": "Annual checkup",
    })
    assert booking.status_code == 201
    assert booking.json()["starts_at"].startswith(starts.date().isoformat())
    assert booking.json()["service_kind"] == "veterinarian"

    assert client.post("/api/v1/appointments", headers=owner_headers, json={
        "pet_id": pet["id"], "availability_id": slot["id"],
    }).status_code == 409
    assert client.get("/api/v1/appointments", headers=owner_headers).json()[0]["id"] == booking.json()["id"]

    another_owner = create_account(client, "another@example.com")
    assert client.get("/api/v1/appointments", headers=another_owner).json() == []
    assert client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=another_owner,
        json={"status": "confirmed"},
    ).status_code == 403

    assert client.get("/api/v1/appointments", headers=provider_headers).json()[0]["id"] == booking.json()["id"]
    confirmed = client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=provider_headers,
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    rescheduled = client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/reschedule",
        headers=owner_headers,
        json={"availability_id": later_slot_response.json()["id"]},
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["status"] == "pending"
    assert rescheduled.json()["availability_id"] == later_slot_response.json()["id"]

    replacement = client.post("/api/v1/appointments", headers=another_owner, json={
        "pet_id": client.post("/api/v1/pets", headers=another_owner, json={
            "name": "Nori", "species": "Cat",
        }).json()["id"],
        "availability_id": slot["id"],
    })
    assert replacement.status_code == 201
    cancelled = client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=owner_headers,
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_only_verified_groomers_can_publish_service_availability(client):
    owner_headers = create_account(client, "new-groomer@example.com")
    forbidden = client.put("/api/v1/providers/me/profile", headers=owner_headers, json={
        "display_name": "Friendly Grooming",
        "bio": "Gentle grooming services for local pets.",
    })
    assert forbidden.status_code == 403

    groomer_headers = approve_role(client, "groomer@example.com", "groomer")
    profile = client.put("/api/v1/providers/me/profile", headers=groomer_headers, json={
        "display_name": "Friendly Grooming",
        "bio": "Gentle grooming services for local pets.",
    })
    assert profile.status_code == 200
    assert profile.json()["kind"] == "groomer"
    providers = client.get("/api/v1/providers?kind=groomer")
    assert providers.status_code == 200
    assert [provider["id"] for provider in providers.json()] == [profile.json()["id"]]
    starts = datetime.now(timezone.utc) + timedelta(days=10)
    slot = client.post("/api/v1/providers/me/availability", headers=groomer_headers, json={
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=1)).isoformat(),
    })
    assert slot.status_code == 201
    pet_owner = create_account(client, "grooming-customer@example.com")
    pet = client.post("/api/v1/pets", headers=pet_owner, json={
        "name": "Cleo", "species": "Cat",
    }).json()
    booking = client.post("/api/v1/appointments", headers=pet_owner, json={
        "pet_id": pet["id"], "availability_id": slot.json()["id"],
    })
    assert booking.status_code == 201
    assert booking.json()["service_kind"] == "groomer"


def test_emergency_assignment_hides_location_and_notifies_authorized_users(client):
    owner_headers = create_account(client, "emergency-owner@example.com")
    pet = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Sunny", "species": "Dog",
    }).json()
    request = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "suspected_poisoning",
        "severity": "critical",
        "description": "May have swallowed an unknown garden chemical.",
        "pet_id": pet["id"],
        "location": "North District, near the central park",
    })
    assert request.status_code == 201
    request_id = request.json()["id"]
    assert request.json()["status"] == "submitted"
    assert request.json()["location"] == "North District, near the central park"

    volunteer_headers = approve_role(client, "volunteer@example.com", "volunteer")
    assert client.put("/api/v1/volunteers/me/profile", headers=volunteer_headers, json={
        "service_area": "South District",
        "is_available": True,
    }).status_code == 200
    assert client.get("/api/v1/emergencies/available", headers=volunteer_headers).json() == []
    assert client.get(f"/api/v1/emergencies/{request_id}", headers=volunteer_headers).status_code == 404
    assert client.post(f"/api/v1/emergencies/{request_id}/accept", headers=volunteer_headers).status_code == 404

    assert client.put("/api/v1/volunteers/me/profile", headers=volunteer_headers, json={
        "service_area": "North District",
        "is_available": True,
    }).status_code == 200
    available = client.get("/api/v1/emergencies/available", headers=volunteer_headers)
    assert available.status_code == 200
    assert len(available.json()) == 1
    assert available.json()[0]["location"] is None
    assert client.get(f"/api/v1/emergencies/{request_id}", headers=volunteer_headers).json()["location"] is None

    another_volunteer = approve_role(client, "volunteer-two@example.com", "volunteer")
    assert client.put("/api/v1/volunteers/me/profile", headers=another_volunteer, json={
        "service_area": "North District",
        "is_available": True,
    }).status_code == 200

    assigned = client.post(f"/api/v1/emergencies/{request_id}/accept", headers=volunteer_headers)
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["assigned_volunteer_id"] is not None
    assert assigned.json()["location"] == "North District, near the central park"
    assigned_queue = client.get("/api/v1/emergencies/available", headers=volunteer_headers)
    assert assigned_queue.status_code == 200
    assert assigned_queue.json()[0]["id"] == request_id
    assert assigned_queue.json()[0]["location"] == "North District, near the central park"
    assert client.post(f"/api/v1/emergencies/{request_id}/accept", headers=another_volunteer).status_code == 409
    assert client.get(f"/api/v1/emergencies/{request_id}", headers=another_volunteer).status_code == 404
    second_request = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "serious_injury",
        "severity": "urgent",
        "description": "Needs help reaching a nearby animal clinic.",
        "pet_id": pet["id"],
        "location": "North District",
    })
    assert second_request.status_code == 201
    assert client.put("/api/v1/volunteers/me/profile", headers=volunteer_headers, json={
        "service_area": "North District",
        "is_available": True,
    }).status_code == 200
    assert client.post(
        f"/api/v1/emergencies/{second_request.json()['id']}/accept",
        headers=volunteer_headers,
    ).status_code == 409

    responding = client.patch(f"/api/v1/emergencies/{request_id}/status", headers=volunteer_headers, json={
        "status": "responding",
    })
    assert responding.status_code == 200
    assert responding.json()["status"] == "responding"
    in_progress = client.patch(f"/api/v1/emergencies/{request_id}/status", headers=volunteer_headers, json={
        "status": "in_progress",
    })
    assert in_progress.status_code == 200
    assert client.patch(f"/api/v1/emergencies/{request_id}/status", headers=another_volunteer, json={
        "status": "completed",
    }).status_code == 404
    completed = client.patch(f"/api/v1/emergencies/{request_id}/status", headers=volunteer_headers, json={
        "status": "completed",
    })
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    accepted_next = client.post(
        f"/api/v1/emergencies/{second_request.json()['id']}/accept",
        headers=volunteer_headers,
    )
    assert accepted_next.status_code == 200

    owner_alerts = client.get("/api/v1/notifications", headers=owner_headers)
    assert owner_alerts.status_code == 200
    assert len(owner_alerts.json()) == 7
    assert all(notification["kind"] == "emergency" for notification in owner_alerts.json())
    notification_id = owner_alerts.json()[0]["id"]
    assert client.patch(f"/api/v1/notifications/{notification_id}/read", headers=another_volunteer).status_code == 404
    assert client.patch(f"/api/v1/notifications/{notification_id}/read", headers=owner_headers).json()["is_read"] is True


def test_emergency_permissions_and_owner_cancellation(client):
    owner_headers = create_account(client, "stray-helper@example.com")
    other_owner = create_account(client, "other-helper@example.com")
    other_pet = client.post("/api/v1/pets", headers=other_owner, json={
        "name": "Mochi", "species": "Cat",
    }).json()
    forbidden_pet = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "injured_stray",
        "severity": "urgent",
        "description": "An injured animal is near the road.",
        "pet_id": other_pet["id"],
    })
    assert forbidden_pet.status_code == 404
    created = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "injured_stray",
        "severity": "urgent",
        "description": "An injured animal is near the road.",
        "location": "West neighborhood",
    })
    assert created.status_code == 201
    request_id = created.json()["id"]
    assert created.json()["pet_id"] is None
    assert client.get("/api/v1/emergencies/mine", headers=other_owner).json() == []
    assert client.get("/api/v1/emergencies/available", headers=owner_headers).status_code == 403
    assert client.patch(f"/api/v1/emergencies/{request_id}/status", headers=other_owner, json={
        "status": "cancelled",
    }).status_code == 404
    cancelled = client.patch(f"/api/v1/emergencies/{request_id}/status", headers=owner_headers, json={
        "status": "cancelled",
    })
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.patch(f"/api/v1/emergencies/{request_id}/status", headers=owner_headers, json={
        "status": "cancelled",
    }).status_code == 403


def test_volunteer_can_decline_without_hiding_request_from_others(client):
    owner_headers = create_account(client, "decline-owner@example.com")
    created = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "other",
        "severity": "urgent",
        "description": "Need help transporting an animal to a shelter.",
        "location": "East District",
    })
    request_id = created.json()["id"]

    declining_volunteer = approve_role(client, "declining-volunteer@example.com", "volunteer")
    assert client.put("/api/v1/volunteers/me/profile", headers=declining_volunteer, json={
        "service_area": "East District",
        "is_available": True,
    }).status_code == 200
    assert client.post(f"/api/v1/emergencies/{request_id}/decline", headers=declining_volunteer).status_code == 204
    assert client.get("/api/v1/emergencies/available", headers=declining_volunteer).json() == []
    assert client.post(f"/api/v1/emergencies/{request_id}/decline", headers=declining_volunteer).status_code == 409

    next_volunteer = approve_role(client, "next-volunteer@example.com", "volunteer")
    assert client.put("/api/v1/volunteers/me/profile", headers=next_volunteer, json={
        "service_area": "East District",
        "is_available": True,
    }).status_code == 200
    eligible = client.get("/api/v1/emergencies/available", headers=next_volunteer)
    assert [item["id"] for item in eligible.json()] == [request_id]


def test_appointment_messaging_is_limited_to_participants_and_notifies_recipient(client):
    provider_headers = approve_role(client, "messaging-vet@example.com", "veterinarian")
    profile = client.put("/api/v1/providers/me/profile", headers=provider_headers, json={
        "display_name": "Messaging Vet Clinic",
        "bio": "Preventative and routine care for local companion animals.",
    }).json()
    starts = datetime.now(timezone.utc) + timedelta(days=12)
    slot = client.post("/api/v1/providers/me/availability", headers=provider_headers, json={
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(minutes=30)).isoformat(),
    }).json()
    owner_headers = create_account(client, "message-owner@example.com")
    pet = client.post("/api/v1/pets", headers=owner_headers, json={
        "name": "Hazel", "species": "Rabbit",
    }).json()
    appointment = client.post("/api/v1/appointments", headers=owner_headers, json={
        "pet_id": pet["id"], "availability_id": slot["id"],
    }).json()

    opened = client.post("/api/v1/conversations", headers=owner_headers, json={
        "context_type": "appointment", "context_id": appointment["id"],
    })
    assert opened.status_code == 200
    conversation = opened.json()
    assert conversation["appointment_id"] == appointment["id"]
    assert conversation["other_user_name"] == "Pet Owner"

    provider_opened = client.post("/api/v1/conversations", headers=provider_headers, json={
        "context_type": "appointment", "context_id": appointment["id"],
    })
    assert provider_opened.status_code == 200
    assert provider_opened.json()["id"] == conversation["id"]

    stranger = create_account(client, "message-stranger@example.com")
    assert client.post("/api/v1/conversations", headers=stranger, json={
        "context_type": "appointment", "context_id": appointment["id"],
    }).status_code == 404
    assert client.get("/api/v1/conversations", headers=stranger).json() == []
    assert client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=stranger).status_code == 404
    assert client.post(f"/api/v1/conversations/{conversation['id']}/messages", headers=stranger, json={
        "body": "Private message",
    }).status_code == 404

    sent = client.post(f"/api/v1/conversations/{conversation['id']}/messages", headers=owner_headers, json={
        "body": "Could we discuss Hazel's upcoming checkup?",
    })
    assert sent.status_code == 201
    assert sent.json()["sender_name"] == "Pet Owner"
    provider_alerts = client.get("/api/v1/notifications", headers=provider_headers).json()
    assert len(provider_alerts) == 1
    assert provider_alerts[0]["kind"] == "message"

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=provider_headers)
    assert messages.status_code == 200
    assert len(messages.json()) == 1
    assert messages.json()[0]["read_at"] is not None
    owner_conversations = client.get("/api/v1/conversations", headers=owner_headers).json()
    assert owner_conversations[0]["unread_count"] == 0


def test_emergency_conversation_requires_assigned_owner_or_volunteer(client):
    owner_headers = create_account(client, "emergency-chat-owner@example.com")
    request = client.post("/api/v1/emergencies", headers=owner_headers, json={
        "category": "injured_stray",
        "severity": "urgent",
        "description": "Need a volunteer to coordinate safe transport.",
    }).json()
    volunteer_headers = approve_role(client, "emergency-chat-volunteer@example.com", "volunteer")
    client.put("/api/v1/volunteers/me/profile", headers=volunteer_headers, json={
        "service_area": "Central",
        "is_available": True,
    })
    client.post(f"/api/v1/emergencies/{request['id']}/accept", headers=volunteer_headers)

    opened = client.post("/api/v1/conversations", headers=owner_headers, json={
        "context_type": "emergency", "context_id": request["id"],
    })
    assert opened.status_code == 200
    volunteer_opened = client.post("/api/v1/conversations", headers=volunteer_headers, json={
        "context_type": "emergency", "context_id": request["id"],
    })
    assert volunteer_opened.status_code == 200
    assert volunteer_opened.json()["id"] == opened.json()["id"]

    stranger = create_account(client, "emergency-chat-stranger@example.com")
    assert client.post("/api/v1/conversations", headers=stranger, json={
        "context_type": "emergency", "context_id": request["id"],
    }).status_code == 404
    assert client.post(f"/api/v1/conversations/{opened.json()['id']}/messages", headers=owner_headers, json={
        "body": "Please call the clinic on arrival.",
    }).status_code == 201
    assert client.get(f"/api/v1/conversations/{opened.json()['id']}/messages", headers=stranger).status_code == 404
