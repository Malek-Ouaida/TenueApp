import re
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, ProgrammingError
from starlette.requests import Request

from app.api.router import api_router
from app.core.config import settings
from app.core.database_status import classify_database_failure

app = FastAPI(
    title=settings.app_name,
    version="0.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except (OperationalError, ProgrammingError) as exc:
        failure = classify_database_failure(exc)
        if failure is None:
            raise

        payload = {"detail": failure.message, "code": failure.code}
        if failure.expected_revisions:
            payload["expected_revisions"] = list(failure.expected_revisions)
        response = JSONResponse(status_code=failure.status_code, content=payload)
        _attach_cors_headers(request=request, response=response)
    response.headers["X-Request-ID"] = request_id
    return response


def _attach_cors_headers(*, request: Request, response: JSONResponse) -> None:
    origin = request.headers.get("Origin")
    if not origin:
        return

    allowed_origin = origin.rstrip("/")
    if allowed_origin in settings.cors_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    elif settings.cors_allow_origin_regex and re.match(settings.cors_allow_origin_regex, origin):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        return

    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Vary"] = "Origin"


app.include_router(api_router)
