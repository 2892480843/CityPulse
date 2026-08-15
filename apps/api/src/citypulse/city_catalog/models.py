import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citypulse.shared.orm import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(sa.String(12), unique=True)
    name: Mapped[str] = mapped_column(sa.String(64), index=True)
    province: Mapped[str] = mapped_column(sa.String(32))
    valid_from: Mapped[date | None] = mapped_column(sa.Date)
    valid_to: Mapped[date | None] = mapped_column(sa.Date)

    aliases: Mapped[list["CityAlias"]] = relationship(
        back_populates="city", cascade="all, delete-orphan", lazy="selectin"
    )


class CityAlias(Base):
    __tablename__ = "city_aliases"

    city_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(sa.String(64), primary_key=True)

    city: Mapped[City] = relationship(back_populates="aliases")
