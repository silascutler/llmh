from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.auth.passwords import hash_password
from llmh.db.models import User


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def set_password(session: AsyncSession, user: User, password: str) -> User:
    user.password_hash = hash_password(password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_user(session: AsyncSession, *, username: str, password: str, role: str) -> User:
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(user)
    return user


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.asc(), User.username.asc()))
    return list(result.scalars())


async def delete_user(session: AsyncSession, user: User) -> None:
    if user.role == "admin":
        result = await session.execute(select(func.count()).select_from(User).where(User.role == "admin"))
        admin_count = int(result.scalar_one())
        if admin_count <= 1:
            raise ValueError("cannot delete the last admin user")
    await session.delete(user)
    await session.commit()
