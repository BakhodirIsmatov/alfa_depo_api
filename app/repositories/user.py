from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.access import Role
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.role))
        )
        return result.scalar_one_or_none()

    async def get_by_identity(self, identity: str) -> User | None:
        normalized = identity.strip().lower()
        result = await self.session.execute(
            select(User)
            .where(
                or_(User.username == normalized, User.email == normalized),
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.role))
        )
        return result.scalar_one_or_none()

    async def identity_exists(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        exclude_id: int | None = None,
    ) -> bool:
        clauses = []
        if username is not None:
            clauses.append(User.username == username)
        if email is not None:
            clauses.append(User.email == email)
        if not clauses:
            return False
        statement = select(User.id).where(or_(*clauses))
        if exclude_id is not None:
            statement = statement.where(User.id != exclude_id)
        return (await self.session.execute(statement.limit(1))).scalar_one_or_none() is not None

    async def list(
        self,
        page: int,
        page_size: int,
        *,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        include_deleted: bool = False,
        sort_by: str = "id",
        sort_order: str = "asc",
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
        activity_from: datetime | None = None,
        activity_to: datetime | None = None,
    ) -> tuple[list[User], int]:
        filters = []
        if not include_deleted:
            filters.append(User.deleted_at.is_(None))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        if role:
            filters.append(User.role.has(Role.code == role))
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        if last_login_from:
            filters.append(User.last_login_at >= last_login_from)
        if last_login_to:
            filters.append(User.last_login_at <= last_login_to)
        if activity_from:
            filters.append(User.last_activity_at >= activity_from)
        if activity_to:
            filters.append(User.last_activity_at <= activity_to)
        total = await self.session.scalar(select(func.count()).select_from(User).where(*filters))
        columns = {
            "id": User.id,
            "username": User.username,
            "full_name": User.full_name,
            "last_login_at": User.last_login_at,
            "last_activity_at": User.last_activity_at,
            "created_at": User.created_at,
        }
        column = columns[sort_by]
        ordering = column.desc().nullslast() if sort_order == "desc" else column.asc().nullsfirst()
        result = await self.session.execute(
            select(User)
            .where(*filters)
            .options(selectinload(User.role))
            .order_by(ordering, User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars()), int(total or 0)

    async def count_active_admins(self, admin_role_id: int, *, for_update: bool = False) -> int:
        statement = select(User).where(
            User.role_id == admin_role_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return len(list((await self.session.scalars(statement)).all()))

    def add(self, user: User) -> None:
        self.session.add(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
