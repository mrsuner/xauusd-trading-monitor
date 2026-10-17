#!/usr/bin/env python3
"""Synthetic configuration and role-boundary tests; never require production envs."""
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

INFRA=Path(__file__).resolve().parents[2]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


CFG=module('shared82',INFRA/'scripts/shared82.py')
PUBLIC=module('shared82_public',INFRA/'scripts/shared82-public-entrypoint.py')


class Shared82Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory(prefix='xauusd-static-') as temp:
            root=Path(temp);shutil.copy2(INFRA/'docker-compose.shared82.yml',root/'docker-compose.shared82.yml')
            url=lambda role:'postgresql://'+role+':synthetic-only-password@shared-postgres:5432/xauusd_public'
            notification=dict(DB_CONNECTION='pgsql',DB_URL=url('xauusd_notify_runtime'),DB_SEARCH_PATH='notify,public',
                APP_KEY='synthetic-key',REDIS_HOST='shared-redis-state',REDIS_USERNAME='xauusd_state',REDIS_PASSWORD='synthetic-state',
                REDIS_DB='0',REDIS_CACHE_DB='0',REDIS_URL='',REDIS_PREFIX='xauusd:',HORIZON_PREFIX='xauusd:horizon:',CACHE_STORE='redis',REDIS_QUEUE_RETRY_AFTER='240')
            values=[dict(XAUUSD_PUBLIC_IMAGE=CFG.PUBLIC_IMAGE,XAUUSD_NOTIFICATION_IMAGE=CFG.NOTIFICATION_IMAGE),
                    dict(PUBLIC_DATABASE_URL=url('xauusd_runtime')),dict(PUBLIC_DATABASE_URL=url('xauusd_migrator')),
                    notification,dict(DB_CONNECTION='pgsql',DB_SEARCH_PATH='notify,public',DB_URL=url('xauusd_notify_migrator'),NOTIFICATION_ENABLED='false',NOTIFICATION_DRY_RUN='true',DIGEST_ENABLED='false',CACHE_STORE='array',REDIS_HOST='127.0.0.1')]
            for part,data in zip(CFG.PARTS,values):
                p=root/('.env.shared82.'+part);p.write_text(CFG.raw(data));p.chmod(0o600)
            original=CFG.INFRA
            try:CFG.INFRA=root;cls.model=CFG.render()
            finally:CFG.INFRA=original

    def rejects(self,change):
        value=copy.deepcopy(self.model);change(value)
        with self.assertRaises(ValueError):CFG.validate(value)

    def test_notify_cannot_use_public_owner_credentials(self):
        self.rejects(lambda m:m['services']['notification-api']['environment'].update(DB_URL='postgresql://xauusd_migrator:fake@shared-postgres:5432/xauusd_public'))

    def test_runtime_cannot_use_an_unreviewed_image(self):
        self.rejects(lambda m:m['services']['public-api'].update(image='postgres:latest'))

    def test_long_jobs_cannot_use_the_old_retry_or_grace(self):
        self.rejects(lambda m:m['services']['notification-horizon']['environment'].update(REDIS_QUEUE_RETRY_AFTER='60'))
        self.rejects(lambda m:m['services']['notification-horizon'].update(stop_grace_period='3m0s'))

    def test_migrator_cannot_join_egress_or_receive_fcm_keys(self):
        self.rejects(lambda m:m['services']['notification-migrate']['networks'].update(edge=None))
        self.rejects(lambda m:m['services']['notification-migrate']['environment'].update(FCM_SECRET='synthetic-only'))

    def test_public_host_ports_and_mutable_bind_mounts_are_rejected(self):
        self.rejects(lambda m:m['services']['public-api'].update(ports=[{'target':8080,'published':'8080'}]))
        self.rejects(lambda m:m['services']['notification-api']['volumes'][0].update(read_only=False))

    def test_public_entrypoint_rejects_runtime_migration_and_wrong_role(self):
        env=dict(XAUUSD_SHARED82_ROLE='public-runtime',PUBLIC_DATABASE_URL='postgresql://xauusd_runtime:fake@shared-postgres:5432/xauusd_public')
        PUBLIC.validate(env,['public-api','run'])
        with self.assertRaises(ValueError):PUBLIC.validate(env,['alembic','-c','alembic.ini','upgrade','head'])
        env['PUBLIC_DATABASE_URL']='postgresql://xauusd_migrator:fake@shared-postgres:5432/xauusd_public'
        with self.assertRaises(ValueError):PUBLIC.validate(env,['public-api','run'])

    def test_notification_entrypoint_rejects_runtime_ddl_before_bootstrap(self):
        env=dict(PATH='/usr/bin:/bin',XAUUSD_SHARED82_ROLE='notify-runtime',REDIS_HOST='shared-redis-state',
                 REDIS_USERNAME='xauusd_state',REDIS_DB='0',REDIS_CACHE_DB='0',REDIS_PREFIX='xauusd:',
                 HORIZON_PREFIX='xauusd:horizon:',CACHE_STORE='redis',REDIS_QUEUE_RETRY_AFTER='240')
        p=subprocess.run(['/bin/sh',str(INFRA/'scripts/shared82-notification-entrypoint.sh'),'php','artisan','migrate','--force'],env=env,capture_output=True,timeout=5)
        self.assertEqual(64,p.returncode);self.assertIn(b'runtime command',p.stderr)


if __name__=='__main__':unittest.main()
