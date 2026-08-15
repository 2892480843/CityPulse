"""Create the initial CityPulse users from the command line.

Usage inside the API container or virtual environment:

    python -m citypulse.identity.bootstrap --username admin --roles admin

The password is read from --password-env (recommended) or --password.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from citypulse.identity.models import RoleName
from citypulse.identity.service import create_user, ensure_roles_seeded
from citypulse.shared.config import get_settings


async def bootstrap(
    database_url: str,
    *,
    username: str,
    password: str,
    display_name: str,
    roles: list[RoleName],
) -> None:
    engine = create_async_engine(database_url)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            await ensure_roles_seeded(db)
            user = await create_user(
                db,
                username=username,
                password=password,
                display_name=display_name,
                roles=roles,
            )
            await db.commit()
            print(f"Created user {user.username} with roles {sorted(roles)}")
    finally:
        await engine.dispose()


def parse_roles(raw: str) -> list[RoleName]:
    roles: list[RoleName] = []
    for name in raw.split(","):
        name = name.strip().lower()
        if not name:
            continue
        if name not in ("admin", "analyst", "operator"):
            raise SystemExit(f"Unknown role: {name}. Use admin, analyst, or operator.")
        roles.append(name)  # type: ignore[arg-type]
    if not roles:
        raise SystemExit("At least one role is required.")
    return roles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an initial CityPulse user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--roles", default="admin")
    parser.add_argument("--password-env", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args(argv)

    if args.password is not None:
        password = args.password
    elif args.password_env is not None:
        password = os.environ.get(args.password_env, "")
        if not password:
            print(f"Environment variable {args.password_env} is empty.", file=sys.stderr)
            return 2
    else:
        password = getpass.getpass(f"Password for {args.username}: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 2

    asyncio.run(
        bootstrap(
            get_settings().database_url,
            username=args.username,
            password=password,
            display_name=args.display_name or args.username,
            roles=parse_roles(args.roles),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
