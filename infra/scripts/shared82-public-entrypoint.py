#!/usr/bin/env python3
"""Validate the shared database role before executing the unchanged API image."""
import os
import sys
from urllib.parse import urlsplit


def validate(env, command):
    role=env.get('XAUUSD_SHARED82_ROLE')
    expected={'public-runtime':'xauusd_runtime','public-migrator':'xauusd_migrator'}.get(role)
    url=urlsplit(env.get('PUBLIC_DATABASE_URL',''))
    if not expected or url.scheme not in ('postgres','postgresql') or url.hostname!='shared-postgres' or url.port!=5432 or url.path!='/xauusd_public' or url.username!=expected or not url.password or url.query or url.fragment:
        raise ValueError('Public database role/host binding rejected')
    allowed=[['public-api','run']] if role=='public-runtime' else [['alembic','-c','alembic.ini','upgrade','head'],['alembic','-c','alembic.ini','current']]
    if command not in allowed:
        raise ValueError('Public service command rejected')


if __name__=='__main__':
    try:
        validate(os.environ,sys.argv[1:])
    except (ValueError,TypeError):
        print('Shared82 public entrypoint rejected configuration; diagnostics suppressed',file=sys.stderr);sys.exit(64)
    os.execvp(sys.argv[1],sys.argv[1:])
