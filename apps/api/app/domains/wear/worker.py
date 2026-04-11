from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.domains.wear.models import WearEventJob, WearProcessingRunType
from app.domains.wear.repository import WearJobRepository

JobHandler = Callable[[Session, WearEventJob], None]


class WearWorker:
    def __init__(
        self,
        *,
        session: Session,
        handlers: Mapping[WearProcessingRunType, JobHandler] | None = None,
    ) -> None:
        self.session = session
        self.repository = WearJobRepository(session)
        self.handlers = dict(handlers or {})

    def run_once(self, *, worker_name: str) -> WearEventJob | None:
        job = self.repository.claim_next_job(worker_name=worker_name)
        if job is None:
            self.session.commit()
            return None

        handler = self.handlers.get(job.job_kind)
        if handler is None:
            self.repository.handle_job_failure(
                job=job,
                error_code="unsupported_job_handler",
                error_detail=f"No handler registered for {job.job_kind.value}.",
                retryable=False,
            )
            self.session.commit()
            return job

        try:
            handler(self.session, job)
        except Exception as exc:
            self.repository.handle_job_failure(
                job=job,
                error_code="job_handler_failed",
                error_detail=str(exc),
                retryable=True,
            )
            self.session.commit()
            return job

        self.repository.mark_job_completed(job=job)
        self.session.commit()
        return job


def run_once(
    worker_name: str,
    *,
    handlers: Mapping[WearProcessingRunType, JobHandler] | None = None,
) -> UUID | None:
    session = SessionLocal()
    try:
        worker = WearWorker(session=session, handlers=handlers)
        job = worker.run_once(worker_name=worker_name)
        return job.id if job is not None else None
    finally:
        session.close()
