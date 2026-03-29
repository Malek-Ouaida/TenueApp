from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.domains.closet.errors import UNSUPPORTED_JOB_HANDLER, ClosetDomainError
from app.domains.closet.models import ClosetJob, ProcessingRunType
from app.domains.closet.repository import ClosetJobRepository

JobHandler = Callable[[Session, ClosetJob], None]


class ClosetWorker:
    def __init__(
        self,
        *,
        session: Session,
        handlers: Mapping[ProcessingRunType, JobHandler] | None = None,
    ) -> None:
        self.session = session
        self.repository = ClosetJobRepository(session)
        self.handlers = dict(handlers or {})

    def run_once(self, *, worker_name: str) -> ClosetJob | None:
        job = self.repository.claim_next_job(worker_name=worker_name)
        if job is None:
            self.session.commit()
            return None

        handler = self.handlers.get(job.job_kind)
        if handler is None:
            self.repository.mark_job_failed(
                job=job,
                error_code=UNSUPPORTED_JOB_HANDLER,
                error_detail=f"No handler registered for {job.job_kind.value}.",
            )
            self.session.commit()
            return job

        try:
            handler(self.session, job)
        except Exception as exc:
            self.repository.mark_job_failed(
                job=job,
                error_code=exc.code if isinstance(exc, ClosetDomainError) else "job_handler_failed",
                error_detail=exc.detail if isinstance(exc, ClosetDomainError) else str(exc),
            )
            self.session.commit()
            return job

        self.repository.mark_job_completed(job=job)
        self.session.commit()
        return job


def run_once(
    worker_name: str,
    *,
    handlers: Mapping[ProcessingRunType, JobHandler] | None = None,
) -> UUID | None:
    session = SessionLocal()
    try:
        worker = ClosetWorker(session=session, handlers=handlers)
        job = worker.run_once(worker_name=worker_name)
        return job.id if job is not None else None
    finally:
        session.close()
