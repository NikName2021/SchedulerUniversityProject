from database.all_models import Stream, StreamGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class GenerationService:
    @staticmethod
    async def get_subjects_summary(
        selected_groups: list[str], enabled_types: list[str], session: AsyncSession
    ) -> dict[str, list[str]]:
        """Returns subjects grouped by direction (prefix before /)"""
        stmt = (
            select(Stream)
            .join(Stream.groups)
            .filter(StreamGroup.group_name.in_(selected_groups))
            .filter(Stream.is_ignored.is_(False))
            .filter(Stream.stream_type.in_(enabled_types))
            .options(selectinload(Stream.groups))
        )
        result = await session.execute(stmt)
        streams = result.unique().scalars().all()

        summary = {}  # { "Direction": set(["Subject1", "Subject2"]) }
        for s in streams:
            # Extract direction: "ИОП-ИТ-25/1" -> "ИОП-ИТ-25"
            for g in s.groups:
                if g.group_name in selected_groups:
                    direction = (
                        g.group_name.split("/")[0]
                        if "/" in g.group_name
                        else "Общее"
                    )
                    if direction not in summary:
                        summary[direction] = set()
                    summary[direction].add(s.event_name)

        return {d: sorted(list(subs)) for d, subs in summary.items()}
