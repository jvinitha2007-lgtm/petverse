from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import AdoptionListing, MissingPetReport, Pet, PetSighting, User
from app.schemas import (
    AdoptionListingCreate,
    AdoptionListingOut,
    AdoptionListingStatus,
    MissingPetCreate,
    MissingPetOut,
    MissingPetStatus,
    PetSightingCreate,
    PetSightingOut,
)

router = APIRouter(prefix="/api/v1")


@router.get("/adoptions", response_model=list[AdoptionListingOut])
def list_adoptions(
    status_filter: str = Query(default="available", alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AdoptionListing]:
    query = select(AdoptionListing)
    if status_filter != "all":
        if status_filter not in ("available", "pending", "adopted", "withdrawn"):
            raise HTTPException(status_code=422, detail="Invalid adoption listing status")
        query = query.where(AdoptionListing.status == status_filter)
    return list(db.scalars(query.order_by(AdoptionListing.created_at.desc()).offset(offset).limit(limit)))


@router.post("/adoptions", response_model=AdoptionListingOut, status_code=status.HTTP_201_CREATED)
def create_adoption(
    payload: AdoptionListingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdoptionListing:
    if user.role != "shelter":
        raise HTTPException(status_code=403, detail="Verified shelter access is required")
    listing = AdoptionListing(shelter_user_id=user.id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.patch("/adoptions/{listing_id}/status", response_model=AdoptionListingOut)
def update_adoption(
    listing_id: int,
    payload: AdoptionListingStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdoptionListing:
    listing = db.get(AdoptionListing, listing_id)
    if listing is None or (listing.shelter_user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Adoption listing not found")
    listing.status = payload.status
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/missing-pets", response_model=list[MissingPetOut])
def list_missing_pets(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MissingPetReport]:
    return list(db.scalars(
        select(MissingPetReport)
        .where(MissingPetReport.status == "missing")
        .order_by(MissingPetReport.created_at.desc())
        .offset(offset)
        .limit(limit)
    ))


@router.post("/missing-pets", response_model=MissingPetOut, status_code=status.HTTP_201_CREATED)
def create_missing_pet(
    payload: MissingPetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MissingPetReport:
    pet_id = payload.pet_id
    if pet_id is not None:
        pet = db.scalar(select(Pet).where(Pet.id == pet_id, Pet.owner_id == user.id, Pet.archived.is_(False)))
        if pet is None:
            raise HTTPException(status_code=404, detail="Pet not found")
        pet_name, species = pet.name, pet.species
    else:
        pet_name, species = payload.pet_name.strip(), payload.species.strip()
        if not pet_name or not species:
            raise HTTPException(status_code=422, detail="Pet name and species are required without a pet profile")
    report = MissingPetReport(
        owner_id=user.id,
        pet_id=pet_id,
        pet_name=pet_name,
        species=species,
        description=payload.description.strip(),
        service_area=payload.service_area.strip(),
        contact_instructions=payload.contact_instructions.strip(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.patch("/missing-pets/{report_id}/status", response_model=MissingPetOut)
def update_missing_status(
    report_id: int,
    payload: MissingPetStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MissingPetReport:
    report = db.get(MissingPetReport, report_id)
    if report is None or (report.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Missing pet report not found")
    report.status = payload.status
    db.commit()
    db.refresh(report)
    return report


@router.get("/missing-pets/{report_id}/sightings", response_model=list[PetSightingOut])
def list_sightings(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PetSighting]:
    report = db.get(MissingPetReport, report_id)
    if report is None or report.status == "closed":
        raise HTTPException(status_code=404, detail="Missing pet report not found")
    return list(db.scalars(
        select(PetSighting)
        .where(PetSighting.report_id == report_id)
        .order_by(PetSighting.created_at.desc())
    ))


@router.post(
    "/missing-pets/{report_id}/sightings",
    response_model=PetSightingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_sighting(
    report_id: int,
    payload: PetSightingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PetSighting:
    report = db.get(MissingPetReport, report_id)
    if report is None or report.status != "missing":
        raise HTTPException(status_code=404, detail="Active missing pet report not found")
    sighting = PetSighting(
        report_id=report.id,
        reporter_id=user.id,
        description=payload.description.strip(),
        service_area=payload.service_area.strip(),
    )
    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    return sighting
