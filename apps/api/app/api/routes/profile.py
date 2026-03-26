from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.profile import get_profile_service
from app.api.schemas.profile import ProfileResponse, ProfileUpdateRequest, ProfileView
from app.domains.auth.models import User
from app.domains.profile.service import ProfileService, ProfileServiceError

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
def read_my_profile(
    current_user: CurrentUser,
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        profile = profile_service.get_my_profile(user=current_user)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_profile_response(profile=profile)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: CurrentUser,
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        profile = profile_service.update_my_profile(user=current_user, payload=payload)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_profile_response(profile=profile)


@router.get("/{username}", response_model=ProfileResponse)
def read_profile_by_username(
    username: str,
    _current_user: CurrentUser,
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        profile = profile_service.get_profile_by_username(username=username)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_profile_response(profile=profile)


def build_profile_response(*, profile: User) -> ProfileResponse:
    return ProfileResponse(profile=ProfileView.model_validate(profile))
