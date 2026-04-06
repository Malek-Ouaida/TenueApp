from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies.closet import get_storage_client
from app.core.storage import ObjectStorageClient
from app.db.session import get_db_session
from app.domains.wear.repository import WearRepository
from app.domains.wear.service import WearService


def get_wear_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> WearService:
    return WearService(
        session=db_session,
        repository=WearRepository(db_session),
        storage=storage_client,
    )
