from fastapi import APIRouter

from app.api.dependencies.auth import CurrentUser
from app.api.schemas.closet import ClosetMetadataOptionsResponse
from app.domains.closet.taxonomy import build_metadata_options

router = APIRouter(prefix="/closet", tags=["closet"])


@router.get("/metadata/options", response_model=ClosetMetadataOptionsResponse)
def read_metadata_options(current_user: CurrentUser) -> ClosetMetadataOptionsResponse:
    del current_user
    return ClosetMetadataOptionsResponse.model_validate(build_metadata_options())
