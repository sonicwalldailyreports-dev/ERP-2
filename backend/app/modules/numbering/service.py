from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import AuditLog, NumberSequence
from app.modules.numbering.repository import NumberSequenceRepository, make_scope_key
from app.modules.numbering.schemas import NumberSequenceCreate, NumberSequenceUpdate


class NumberingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = NumberSequenceRepository(session)

    async def list(self, company_id: UUID, branch_id: UUID | None = None) -> list[NumberSequence]:
        return await self.repository.list(company_id, branch_id)

    async def create(self, data: NumberSequenceCreate, actor_id: UUID, dev: bool) -> NumberSequence:
        if not await self.repository.valid_company(data.company_id):
            raise HTTPException(status_code=404, detail="Company not found.")
        if data.branch_id is not None and not await self.repository.valid_branch(data.company_id, data.branch_id):
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if not dev and not await has_permission(
            self.session, actor_id, "numbering.sequence.create", data.company_id, data.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        if data.financial_year_id is not None:
            year = await self.repository.financial_year(data.company_id, data.financial_year_id)
            if year is None:
                raise HTTPException(status_code=422, detail="Financial year does not belong to this company.")
            if not year.is_active or year.is_closed:
                raise HTTPException(status_code=422, detail="Financial year is not open.")
        scope_key = make_scope_key(
            data.company_id, data.document_type, data.branch_id, data.financial_year_id
        )
        if await self.repository.get_by_scope(
            data.company_id, data.document_type, data.branch_id, data.financial_year_id
        ):
            raise HTTPException(status_code=409, detail="A sequence already exists for this scope.")
        sequence = NumberSequence(scope_key=scope_key, **data.model_dump())
        self.session.add(sequence)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="A sequence already exists for this scope.") from None
        await self._audit(sequence, actor_id, "NUMBER_SEQUENCE_CREATED")
        await self.session.commit()
        await self.session.refresh(sequence)
        return sequence

    async def generate(self, sequence_id: UUID, actor_id: UUID, dev: bool) -> dict:
        sequence = await self.repository.get(sequence_id)
        if sequence is None:
            raise HTTPException(status_code=404, detail="Number sequence not found.")
        if not dev and not await has_permission(
            self.session, actor_id, "numbering.sequence.generate", sequence.company_id, sequence.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        if sequence.financial_year_id is not None:
            year = await self.repository.financial_year(sequence.company_id, sequence.financial_year_id)
            if year is None or not year.is_active or year.is_closed:
                raise HTTPException(status_code=409, detail="Financial year is not open.")
        result = await self.repository.increment(sequence_id)
        if result is None:
            raise HTTPException(status_code=409, detail="Number sequence is inactive.")
        number, sequence = result
        await self._audit(
            sequence,
            actor_id,
            "NUMBER_GENERATED",
            {"number": number, "formatted_number": sequence.format_number(number)},
        )
        await self.session.commit()
        return {
            "sequence_id": sequence.id,
            "number": number,
            "formatted_number": sequence.format_number(number),
        }

    async def update(
        self, sequence_id: UUID, data: NumberSequenceUpdate, actor_id: UUID, dev: bool
    ) -> NumberSequence:
        sequence = await self.repository.get(sequence_id)
        if sequence is None:
            raise HTTPException(status_code=404, detail="Number sequence not found.")
        if not dev and not await has_permission(
            self.session, actor_id, "numbering.sequence.edit", sequence.company_id, sequence.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(sequence, key, value)
        await self._audit(sequence, actor_id, "NUMBER_SEQUENCE_UPDATED", data.model_dump(exclude_unset=True))
        await self.session.commit()
        await self.session.refresh(sequence)
        return sequence

    async def next_number(
        self,
        company_id: UUID,
        document_type: str,
        actor_id: UUID,
        branch_id: UUID | None = None,
        financial_year_id: UUID | None = None,
        dev: bool = False,
    ) -> dict:
        sequence = await self.repository.get_by_scope(
            company_id, document_type, branch_id, financial_year_id
        )
        if sequence is None:
            raise HTTPException(status_code=404, detail="Number sequence not configured for this scope.")
        return await self.generate(sequence.id, actor_id, dev)

    async def _audit(
        self, sequence: NumberSequence, actor_id: UUID, action: str, details: dict | None = None
    ) -> None:
        self.session.add(
            AuditLog(
                company_id=sequence.company_id,
                branch_id=sequence.branch_id,
                user_id=actor_id,
                action=action,
                entity_type="number_sequence",
                entity_id=sequence.id,
                details=json.dumps(details or {}),
            )
        )
