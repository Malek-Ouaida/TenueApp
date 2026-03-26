from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.domains.profile.repository import ProfileRepository
from app.domains.profile.service import ProfileService


def get_profile_service(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ProfileService:
    return ProfileService(
        session=db_session,
        repository=ProfileRepository(db_session),
    )
