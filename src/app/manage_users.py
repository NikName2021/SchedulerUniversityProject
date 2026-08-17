import argparse
import asyncio
import datetime
import getpass
import sys

from core.config import sessionmaker
from database import UserAccount, UserSession
from services.auth_service import hash_password, validate_username
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError


def _read_password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    return password


async def _create_user(args: argparse.Namespace) -> None:
    username = validate_username(args.username)
    password_hash = hash_password(_read_password())
    display_name = args.display_name.strip()
    if not display_name or len(display_name) > 120:
        raise ValueError("Display name must contain 1-120 characters")

    async with sessionmaker() as db:
        user = UserAccount(
            username=username,
            display_name=display_name,
            password_hash=password_hash,
            role=args.role,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(f"User '{username}' already exists") from exc
    print(f"Created {args.role} account '{username}'.")


async def _set_password(args: argparse.Namespace) -> None:
    username = validate_username(args.username)
    password_hash = hash_password(_read_password())

    async with sessionmaker() as db:
        result = await db.execute(
            select(UserAccount).where(UserAccount.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User '{username}' does not exist")
        user.password_hash = password_hash
        user.password_changed_at = datetime.datetime.utcnow()
        user.failed_login_count = 0
        user.locked_until = None
        await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        await db.commit()
    print(f"Updated password and revoked all sessions for '{username}'.")


async def _set_active(args: argparse.Namespace, *, active: bool) -> None:
    username = validate_username(args.username)
    async with sessionmaker() as db:
        result = await db.execute(
            select(UserAccount).where(UserAccount.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User '{username}' does not exist")
        user.is_active = active
        if not active:
            await db.execute(
                delete(UserSession).where(UserSession.user_id == user.id)
            )
        await db.commit()
    state = "enabled" if active else "disabled"
    print(f"Account '{username}' is now {state}.")


async def _list_users(_: argparse.Namespace) -> None:
    async with sessionmaker() as db:
        result = await db.execute(select(UserAccount).order_by(UserAccount.username))
        users = list(result.scalars())
    if not users:
        print("No user accounts found.")
        return
    print("USERNAME\tROLE\tACTIVE\tDISPLAY NAME")
    for user in users:
        print(
            f"{user.username}\t{user.role}\t"
            f"{'yes' if user.is_active else 'no'}\t{user.display_name}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage scheduler user accounts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-user", help="Create an account")
    create_parser.add_argument("--username", required=True)
    create_parser.add_argument("--display-name", required=True)
    create_parser.add_argument(
        "--role",
        choices=("admin", "operator"),
        default="operator",
    )
    create_parser.set_defaults(handler=_create_user)

    password_parser = subparsers.add_parser(
        "set-password",
        help="Change a password and revoke all sessions",
    )
    password_parser.add_argument("--username", required=True)
    password_parser.set_defaults(handler=_set_password)

    disable_parser = subparsers.add_parser("disable-user", help="Disable an account")
    disable_parser.add_argument("--username", required=True)
    disable_parser.set_defaults(
        handler=lambda args: _set_active(args, active=False)
    )

    enable_parser = subparsers.add_parser("enable-user", help="Enable an account")
    enable_parser.add_argument("--username", required=True)
    enable_parser.set_defaults(handler=lambda args: _set_active(args, active=True))

    list_parser = subparsers.add_parser("list-users", help="List accounts")
    list_parser.set_defaults(handler=_list_users)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        asyncio.run(args.handler(args))
    except (KeyboardInterrupt, EOFError):
        print("Cancelled.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
