from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies.closet import get_storage_client
from app.core.storage import ObjectStorageClient
from app.db.session import get_db_session
from app.domains.lookbook.repository import LookbookRepository
from app.domains.lookbook.service import LookbookService
from app.domains.lookbook.upload_service import LookbookUploadService


def get_lookbook_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> LookbookService:
    return LookbookService(
        session=db_session,
        repository=LookbookRepository(db_session),
        storage=storage_client,
    )


def get_lookbook_upload_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> LookbookUploadService:
    return LookbookUploadService(
        session=db_session,
        repository=LookbookRepository(db_session),
        storage=storage_client,
    )
