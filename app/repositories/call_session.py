from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.call_session import CallSession, CallState


class CallSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, call_sid: str, initial_state: CallState = CallState.GREETING
    ) -> CallSession:
        session = CallSession(call_sid=call_sid, state=initial_state, context={})
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_call_sid(self, call_sid: str) -> CallSession | None:
        result = await self.db.execute(
            select(CallSession).where(CallSession.call_sid == call_sid)
        )
        return result.scalar_one_or_none()

    async def update_state(self, call_sid: str, state: CallState) -> CallSession:
        result = await self.db.execute(
            select(CallSession).where(CallSession.call_sid == call_sid)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("CallSession", call_sid)
        session.state = state
        await self.db.flush()
        return session

    async def update_context(self, call_sid: str, context: dict) -> CallSession:
        """Merge new context values — does not overwrite existing keys unless explicitly provided."""
        result = await self.db.execute(
            select(CallSession).where(CallSession.call_sid == call_sid)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("CallSession", call_sid)
        merged = {**session.context, **context}
        session.context = merged
        await self.db.flush()
        return session

    async def get_by_upload_token(self, token: str) -> CallSession | None:
        """Find call session by upload token stored in JSON context."""
        result = await self.db.execute(select(CallSession))
        for session in result.scalars():
            if session.context.get("upload_token") == token:
                return session
        return None
