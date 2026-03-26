from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.domains.auth import models as auth_models  # noqa: E402,F401
