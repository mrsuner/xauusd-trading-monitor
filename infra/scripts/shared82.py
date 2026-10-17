#!/usr/bin/env python3
"""Prepare canonical owner-only inputs and inspect the shared82 model; never deploy."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

INFRA=Path(__file__).resolve().parents[1]
PARTS=('compose','public','public-migrator','notification','notification-migrator')
PUBLIC_IMAGE='ghcr.io/mrsuner/xauusd-trading-monitor/public-api@sha256:ae1fef09a507cc4c1e6b916f0793c9ee066757fe44305170aee5daaaea6d800e'
NOTIFICATION_IMAGE='ghcr.io/mrsuner/xauusd-trading-monitor/notification@sha256:8e5fdc31e2b6f72bc7935d55b9a293a4f51f83383c46377affcfbd404c82bff7'


def require(value,message):
    if not value:raise ValueError(message)


def private(path):
    require(path.is_file() and not path.is_symlink() and not path.stat().st_mode&0o077,'Missing or non-private input: '+path.name)
    return path.read_text()


def raw(values):
    require(all(re.fullmatch(r'[A-Z][A-Z0-9_]*',k) and isinstance(v,str) and '\n' not in v and '\r' not in v for k,v in values.items()),'Unsupported environment assignment')
    return '\n'.join(k+'='+v for k,v in values.items())+'\n'


def prepare(credentials):
    paths=[INFRA/('.env.shared82.'+p) for p in PARTS]
    require(not any(p.exists() or p.is_symlink() for p in paths),'Refusing to overwrite shared82 private inputs')
    # Reuse only the existing canonical aligned inputs; never a development env.
    shared=INFRA.parents[2]/'infra/scripts/vps.py'
    spec=importlib.util.spec_from_file_location('legacy_vps',shared);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    legacy=module.render('xauusd');secrets=json.loads(private(credentials))
    url=lambda role:'postgresql://'+role+':'+secrets[role]+'@shared-postgres:5432/xauusd_public'
    public=dict(legacy['services']['public-api']['environment']);public['PUBLIC_DATABASE_URL']=url('xauusd_runtime')
    notification={k:v for k,v in legacy['services']['notification-api']['environment'].items() if not k.startswith('DB_')}
    notification.update(DB_CONNECTION='pgsql',DB_URL=url('xauusd_notify_runtime'),DB_SEARCH_PATH='notify,public',
                        REDIS_HOST='shared-redis-state',REDIS_USERNAME='xauusd_state',REDIS_PASSWORD=secrets['xauusd_state'],
                        REDIS_PORT='6379',REDIS_DB='0',REDIS_CACHE_DB='0',REDIS_URL='',REDIS_PREFIX='xauusd:',
                        HORIZON_PREFIX='xauusd:horizon:',CACHE_STORE='redis',
                        REDIS_CACHE_CONNECTION='cache',REDIS_CACHE_LOCK_CONNECTION='default',REDIS_QUEUE_RETRY_AFTER='240')
    public_migration=dict(APP_ENV='production',SERVICE_NAME='public-api-migrate',PUBLIC_DATABASE_URL=url('xauusd_migrator'),
                          LOG_LEVEL=public.get('LOG_LEVEL','INFO'),TZ=public.get('TZ','UTC'))
    notify_migration=dict(APP_ENV='production',APP_DEBUG='false',APP_KEY=notification['APP_KEY'],LOG_CHANNEL='stderr',
                          DB_CONNECTION='pgsql',DB_URL=url('xauusd_notify_migrator'),DB_SEARCH_PATH='notify,public',REDIS_HOST='127.0.0.1',
                          CACHE_STORE='array',SESSION_DRIVER='array',QUEUE_CONNECTION='sync',
                          NOTIFICATION_ENABLED='false',NOTIFICATION_DRY_RUN='true',NOTIFICATION_ADMISSION_ENABLED='false',
                          DIGEST_ENABLED='false',NOTIFICATION_DEDUP_ENABLED='false',
                          NOTIFICATION_INTERNAL_SECRET='migration-disabled-internal-secret',NEWS_INTERNAL_SECRET='migration-disabled-news-secret',
                          NOTIFICATION_CHANNEL_FINGERPRINT_KEY='migration-disabled-fingerprint-key')
    compose=dict(XAUUSD_PUBLIC_IMAGE=PUBLIC_IMAGE,XAUUSD_NOTIFICATION_IMAGE=NOTIFICATION_IMAGE)
    for path,values in zip(paths,(compose,public,public_migration,notification,notify_migration)):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(raw(values))
    print('Prepared private shared82 inputs; existing application/provider identities retained. No deployment.')


def invocation():
    files=[INFRA/('.env.shared82.'+p) for p in PARTS]
    for path in files:private(path)
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR','DOCKER_CONFIG')}
    for key,path in zip(('SHARED82_PUBLIC_ENV','SHARED82_PUBLIC_MIGRATOR_ENV','SHARED82_NOTIFICATION_ENV','SHARED82_NOTIFICATION_MIGRATOR_ENV'),files[1:]):env[key]=str(path)
    argv=['docker','--context','default','compose','--project-name','xauusd-shared82','--env-file',str(files[0]),
          '-f',str(INFRA/'docker-compose.shared82.yml'),'--profile','notifications','--profile','migration']
    return argv, env


def render():
    argv, env = invocation()
    result=subprocess.run(argv+['config','--format','json'],env=env,capture_output=True,text=True,timeout=45)
    require(result.returncode==0,'Shared82 Compose rejected; diagnostics suppressed')
    model=json.loads(result.stdout);validate(model);return model


def identity(value,role):
    url=urlsplit(value)
    return url.scheme=='postgresql' and url.hostname=='shared-postgres' and url.port==5432 and url.username==role and url.path=='/xauusd_public' and bool(url.password) and not url.query and not url.fragment


def validate(model):
    require(model['name']=='xauusd-shared82','Wrong shared82 project')
    services=model['services'];require(set(services)=={'public-api','public-api-migrate','notification-api','notification-horizon','notification-scheduler','notification-migrate'},'Unexpected services')
    roles={'public-api':'public-runtime','public-api-migrate':'public-migrator','notification-migrate':'notify-migrator'}
    for name,s in services.items():
        notification=name.startswith('notification')
        require(s['image']==(NOTIFICATION_IMAGE if notification else PUBLIC_IMAGE) and s.get('pull_policy')=='never','Unexpected/unpinned image')
        require(not s.get('ports') and not s.get('build') and not s.get('depends_on'),'Ports/build/implicit migration forbidden')
        require(s['environment']['XAUUSD_SHARED82_ROLE']==roles.get(name,'notify-runtime'),'Application role mismatch')
        expected_role='xauusd_notify_migrator' if name=='notification-migrate' else 'xauusd_notify_runtime' if notification else 'xauusd_migrator' if name=='public-api-migrate' else 'xauusd_runtime'
        require(identity(s['environment']['DB_URL' if notification else 'PUBLIC_DATABASE_URL'],expected_role),'Database role mismatch')
        migration=name.endswith('migrate')
        expected_networks={'data'} if migration else {'app','data','tickbase'} if name=='notification-api' else {'app','data','edge'}
        require(set(s['networks'])==expected_networks,'Network scope mismatch')
        mounts=s.get('volumes',[])
        expected_guard='shared82-notification-entrypoint.sh' if notification else 'shared82-public-entrypoint.py'
        require(len(mounts)==1 and mounts[0]['type']=='bind' and mounts[0].get('read_only') is True
                and Path(mounts[0]['source']).name==expected_guard and mounts[0]['target']=='/opt/ops/'+expected_guard,'Unexpected guard/data mount')
        if not migration:require(s.get('init') is True,'Runtime init required')
        if notification and not migration:
            e=s['environment']
            required=dict(DB_CONNECTION='pgsql',DB_SEARCH_PATH='notify,public',REDIS_HOST='shared-redis-state',REDIS_USERNAME='xauusd_state',REDIS_DB='0',REDIS_CACHE_DB='0',
                          REDIS_URL='',REDIS_PREFIX='xauusd:',HORIZON_PREFIX='xauusd:horizon:',CACHE_STORE='redis',REDIS_QUEUE_RETRY_AFTER='240')
            require(all(e.get(k)==v for k,v in required.items()),'Notification state binding mismatch')
            require(s.get('stop_signal')==('SIGINT' if name=='notification-api' else 'SIGTERM'),'CLI stop signal mismatch')
        if name=='notification-migrate':
            e=s['environment']
            require(e.get('NOTIFICATION_ENABLED')=='false' and e.get('NOTIFICATION_DRY_RUN')=='true' and e.get('DIGEST_ENABLED')=='false'
                    and e.get('CACHE_STORE')=='array' and e.get('REDIS_HOST')=='127.0.0.1','Migrator provider isolation mismatch')
            require(not any(k.startswith(('TELEGRAM_','FIREBASE_','FCM_','SMTP_')) for k in e),'Provider credentials in migrator')
            allowed={'APP_ENV','APP_DEBUG','APP_KEY','LOG_CHANNEL','DB_CONNECTION','DB_URL','DB_SEARCH_PATH','REDIS_HOST','CACHE_STORE','SESSION_DRIVER','QUEUE_CONNECTION',
                     'NOTIFICATION_ENABLED','NOTIFICATION_DRY_RUN','NOTIFICATION_ADMISSION_ENABLED','DIGEST_ENABLED','NOTIFICATION_DEDUP_ENABLED',
                     'NOTIFICATION_INTERNAL_SECRET','NEWS_INTERNAL_SECRET','NOTIFICATION_CHANNEL_FINGERPRINT_KEY','XAUUSD_SHARED82_ROLE'}
            require(set(e)<=allowed and e.get('DB_CONNECTION')=='pgsql' and e.get('DB_SEARCH_PATH')=='notify,public','Unexpected migration configuration/credential')
        if name=='public-api-migrate':
            require(set(s['environment'])<={'APP_ENV','SERVICE_NAME','PUBLIC_DATABASE_URL','LOG_LEVEL','TZ','XAUUSD_SHARED82_ROLE'},'Public migrator credentials exceed its allowlist')
    require(services['notification-horizon']['stop_grace_period']=='4m0s','Horizon grace must cover the180s job')
    require(not model.get('volumes'),'Shared model must not create independent datastores')
    require(model['networks']['data'].get('external') and model['networks']['data']['name']=='platform82_xauusd_data','Data network mismatch')
    require('xauusd-public-api' in services['public-api']['networks']['edge']['aliases']
            and 'xauusd-notification' in services['notification-api']['networks']['tickbase']['aliases'],'Existing ingress aliases missing')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',nargs='?',default='config',choices=['prepare','config','images','ps']);parser.add_argument('--platform-credentials',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':require(args.platform_credentials is not None,'Explicit credential map required');prepare(args.platform_credentials)
    elif args.action=='ps':
        render()
        result=subprocess.run(['docker','--context','default','ps','--all','--filter','label=com.docker.compose.project=xauusd-shared82',
                               '--format','table {{.Names}}\t{{.Status}}\t{{.Image}}'],capture_output=True,text=True,timeout=30)
        require(result.returncode==0,'Status query failed');print(result.stdout,end='')
    else:
        model=render();print(json.dumps({k:v['image'] for k,v in model['services'].items()} if args.action=='images' else
                                      dict(static_valid=True,mutation_performed=False,existing_images_reused=True,notification_cache_purpose='authoritative state'),indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,subprocess.SubprocessError):
        print('Shared82 configuration rejected; private diagnostics suppressed',file=sys.stderr);sys.exit(1)
