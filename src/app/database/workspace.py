"""Personal data boundaries shared by HTTP requests and generation workers."""

from sqlalchemy import Column, ForeignKey, Integer, event, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, declared_attr, with_loader_criteria


class WorkspaceAccessError(LookupError):
    """A referenced object is not available in the current workspace."""


class WorkspaceOwned:
    @declared_attr
    def owner_id(cls):
        return Column(
            Integer,
            ForeignKey("user_account.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


def bind_workspace(db: AsyncSession, owner_id: int) -> None:
    """Bind once; a session and its identity map must never cross accounts."""
    previous = db.info.get("workspace_owner_id")
    if previous is not None and previous != owner_id:
        raise WorkspaceAccessError("Cannot switch workspace within a session")
    # Auth loads only account/session rows before binding. Disallow accidentally
    # carrying an object from a privileged lookup into a personal session.
    if any(
        isinstance(item, WorkspaceOwned) and item.owner_id != owner_id
        for item in db.identity_map.values()
    ):
        raise WorkspaceAccessError("Object is not available in this workspace")
    db.info["workspace_owner_id"] = owner_id


async def bind_task_workspace(db: AsyncSession, task_id: int) -> None:
    """Resolve a trusted queue task's owner before any worker data access.

    This narrow Core lookup intentionally reads only ownership, never task
    contents. HTTP endpoints must bind from the authenticated account instead.
    A deleted task gets an empty scope, so delayed callbacks cannot read data.
    """
    from database.all_models import GenerationTask

    connection = await db.connection()
    table = GenerationTask.__table__
    owner_id = await connection.scalar(
        select(table.c.owner_id).where(table.c.id == task_id)
    )
    bind_workspace(db, owner_id if owner_id is not None else -1)


@event.listens_for(Session, "do_orm_execute")
def scope_workspace_queries(state) -> None:
    # Applies to joins, scalar/aggregate selects, eager loads, UPDATE and DELETE.
    # An unbound session sees no personal rows. Roles never bypass this filter.
    if state.is_select or state.is_update or state.is_delete:
        owner_id = state.session.info.get("workspace_owner_id", -1)
        state.statement = state.statement.options(
            with_loader_criteria(
                WorkspaceOwned,
                lambda model: model.owner_id == owner_id,
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def protect_workspace_writes(session, _flush_context, _instances) -> None:
    owner_id = session.info.get("workspace_owner_id")
    objects = session.new.union(session.dirty).union(session.deleted)
    owned = [item for item in objects if isinstance(item, WorkspaceOwned)]
    if not owned:
        return
    if owner_id is None or owner_id < 1:
        raise WorkspaceAccessError("A personal workspace is required")

    for item in owned:
        state = inspect(item)
        if item in session.new and item.owner_id is None:
            item.owner_id = owner_id
        if item.owner_id != owner_id or (
            state.persistent and state.attrs.owner_id.history.has_changes()
        ):
            raise WorkspaceAccessError("Object is not available in this workspace")

    # Check supplied foreign keys as well as relationship assignments. Filtering
    # reads alone would still allow attaching one's rows to another user's IDs.
    references = {}
    for item in owned:
        if item in session.deleted:
            continue
        state = inspect(item)
        for relation in state.mapper.relationships:
            for related in state.attrs[relation.key].history.added:
                if isinstance(related, WorkspaceOwned) and related.owner_id != owner_id:
                    raise WorkspaceAccessError("Related object is not available")
        for column in state.mapper.columns:
            if state.persistent and not state.attrs[column.key].history.has_changes():
                continue
            value = getattr(item, column.key)
            if value is None:
                continue
            for foreign_key in column.foreign_keys:
                target = foreign_key.column
                if "owner_id" in target.table.c:
                    references.setdefault(target, set()).add(value)

    for target, ids in references.items():
        # Parents explicitly added in this flush are not in the database yet.
        pending_ids = {
            getattr(item, target.key)
            for item in session.new
            if isinstance(item, WorkspaceOwned)
            and inspect(item).mapper.local_table is target.table
        }
        ids = ids - pending_ids
        if not ids:
            continue
        found = set(
            session.connection()
            .execute(
                select(target).where(
                    target.in_(ids), target.table.c.owner_id == owner_id
                )
            )
            .scalars()
        )
        if found != ids:
            raise WorkspaceAccessError("Related object is not available")
