from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.auth.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_auth_subject(self, auth_subject: str) -> User | None:
        statement = select(User).where(User.auth_subject == auth_subject)
        return self.session.execute(statement).scalar_one_or_none()

    def sync_from_provider(
        self,
        *,
        email: str,
        auth_provider: str,
        auth_subject: str,
        last_login_at: datetime | None,
    ) -> User:
        user = self.get_by_auth_subject(auth_subject)
        normalized_email = email.strip().lower()

        if user is None:
            user = User(
                email=normalized_email,
                auth_provider=auth_provider,
                auth_subject=auth_subject,
                last_login_at=last_login_at,
            )
            self.session.add(user)
            return user

        user.email = normalized_email
        if last_login_at is not None:
            user.last_login_at = last_login_at

        return user
