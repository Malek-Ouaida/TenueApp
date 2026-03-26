from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx


class AuthProviderError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ProviderUser:
    subject: str
    email: str


@dataclass(frozen=True)
class ProviderSession:
    user: ProviderUser
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    expires_at: datetime | None


@dataclass(frozen=True)
class ProviderRegistration:
    user: ProviderUser
    session: ProviderSession | None
    email_verification_required: bool


class SupabaseAuthProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url.endswith("/auth/v1"):
            normalized_base_url = f"{normalized_base_url}/auth/v1"

        self.base_url = normalized_base_url
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    def sign_up(self, *, email: str, password: str) -> ProviderRegistration:
        payload = self._request_json("POST", "/signup", json={"email": email, "password": password})
        return self._parse_registration(payload)

    def sign_in_with_password(self, *, email: str, password: str) -> ProviderSession:
        payload = self._request_json(
            "POST",
            "/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        return self._parse_session(payload)

    def refresh_session(self, *, refresh_token: str) -> ProviderSession:
        payload = self._request_json(
            "POST",
            "/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
        return self._parse_session(payload)

    def sign_out(self, *, access_token: str) -> None:
        self._request_json("POST", "/logout", access_token=access_token)

    def get_user(self, *, access_token: str) -> ProviderUser:
        payload = self._request_json("GET", "/user", access_token=access_token)
        return self._parse_user(payload)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise AuthProviderError(
                status_code=503,
                detail="SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY is not configured.",
            )

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._build_headers(access_token=access_token),
                    json=json,
                    params=params,
                )
        except httpx.RequestError as exc:
            raise AuthProviderError(
                status_code=503,
                detail="Auth provider is unavailable.",
            ) from exc

        if response.is_success:
            if not response.content:
                return {}
            return cast(dict[str, Any], response.json())

        raise AuthProviderError(
            status_code=response.status_code,
            detail=self._extract_error_detail(response),
        )

    def _build_headers(self, *, access_token: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        if access_token is not None:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _parse_registration(self, payload: dict[str, Any]) -> ProviderRegistration:
        if self._payload_contains_session(payload):
            session = self._parse_session(payload)
            return ProviderRegistration(
                user=session.user,
                session=session,
                email_verification_required=False,
            )

        user_payload = self._extract_user_payload(payload, raw_session_payload=None)
        return ProviderRegistration(
            user=self._parse_user(user_payload),
            session=None,
            email_verification_required=True,
        )

    def _payload_contains_session(self, payload: dict[str, Any]) -> bool:
        raw_session_payload = payload.get("session")
        if isinstance(raw_session_payload, dict):
            return True

        return (
            isinstance(payload.get("access_token"), str)
            and isinstance(payload.get("refresh_token"), str)
            and isinstance(payload.get("token_type"), str)
            and isinstance(payload.get("expires_in"), int)
        )

    def _parse_session(self, payload: dict[str, Any]) -> ProviderSession:
        raw_session_payload = payload.get("session")
        session_payload = raw_session_payload if isinstance(raw_session_payload, dict) else payload
        session_user = self._extract_user_payload(payload, raw_session_payload=session_payload)

        access_token = session_payload.get("access_token")
        refresh_token = session_payload.get("refresh_token")
        token_type = session_payload.get("token_type")
        expires_in = session_payload.get("expires_in")

        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise AuthProviderError(
                status_code=502,
                detail="Auth provider did not return a session.",
            )
        if not isinstance(token_type, str) or not isinstance(expires_in, int):
            raise AuthProviderError(
                status_code=502,
                detail="Auth provider returned an invalid session.",
            )

        expires_at_value = session_payload.get("expires_at")
        expires_at = self._parse_expires_at(expires_at_value, expires_in)

        return ProviderSession(
            user=self._parse_user(session_user),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_in=expires_in,
            expires_at=expires_at,
        )

    def _extract_user_payload(
        self,
        payload: dict[str, Any],
        raw_session_payload: Any,
    ) -> dict[str, Any]:
        if isinstance(raw_session_payload, dict):
            session_user = raw_session_payload.get("user")
            if isinstance(session_user, dict):
                return session_user

        payload_user = payload.get("user")
        if isinstance(payload_user, dict):
            return payload_user

        if isinstance(payload.get("id"), str) and isinstance(payload.get("email"), str):
            return payload

        raise AuthProviderError(status_code=502, detail="Auth provider did not return a user.")

    def _parse_user(self, payload: dict[str, Any]) -> ProviderUser:
        subject = payload.get("id")
        email = payload.get("email")

        if not isinstance(subject, str) or not isinstance(email, str):
            raise AuthProviderError(
                status_code=502,
                detail="Auth provider returned an invalid user.",
            )

        return ProviderUser(subject=subject, email=email)

    def _parse_expires_at(self, value: Any, expires_in: int) -> datetime | None:
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=UTC)
        return datetime.now(UTC) + timedelta(seconds=expires_in)

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Auth provider request failed."

        for key in ("msg", "message", "error_description", "error"):
            detail = payload.get(key)
            if isinstance(detail, str) and detail.strip():
                return detail

        return "Auth provider request failed."
