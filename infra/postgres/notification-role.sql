\set ON_ERROR_STOP on

-- Required psql variables: notification_user, public_owner, database_name.
-- The password is prompted when it is not supplied by a protected caller.
\if :{?notification_password}
\else
\prompt 'Notification database password: ' notification_password
\endif
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'notification_user', :'notification_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'notification_user') \gexec

ALTER ROLE :"notification_user" PASSWORD :'notification_password';
GRANT CONNECT ON DATABASE :"database_name" TO :"notification_user";

CREATE SCHEMA IF NOT EXISTS notify AUTHORIZATION :"notification_user";
ALTER SCHEMA notify OWNER TO :"notification_user";
GRANT USAGE ON SCHEMA public TO :"notification_user";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"notification_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"public_owner" IN SCHEMA public
    GRANT SELECT ON TABLES TO :"notification_user";

REVOKE CREATE ON SCHEMA public FROM :"notification_user";
