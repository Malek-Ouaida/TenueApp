from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.auth.models import User


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.session.execute(statement).scalar_one_or_none()
