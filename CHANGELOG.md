# Changelog

All notable release changes are recorded here. Deployments that predate the
versioned release process are not reconstructed as releases.

## [Unreleased]

## [0.2.0] - 2026-09-23 08:51 UTC

- Moved event summaries to translation rows and added the guarded legacy-field retirement path.
- Added deterministic content-domain routing and public subscription catalog synchronization.
- Added paid News preferences, Telegram linking, durable live delivery, Horizon capacity evidence and account access checks.
- Added shared daily topic digests with frozen inputs, validated citations, English and Traditional Chinese editions, protected reading, partial delivery and withdrawal propagation.
- Added the public notification/digest settings and reading experience.
- Operations: added a disabled-by-default notification Compose profile, restricted database-role contract and dedicated Redis/Horizon runtime.
- Operations: legacy-column cutover/removal, paid admission, notification delivery and digest generation remain independently gated.

## [0.1.0] - 2026-09-11 09:40 UTC

- Added canonical `event_translations` storage and a bounded, verifiable legacy-summary backfill command.
- Moved private event readers and writers to translation rows while retaining legacy summary columns for rollback.
- Added the compatible public `event_type` projection and exposed category/type labels in the public web application.
- Preserved both Traditional Chinese and English summaries during the rehearsed R4 database rollback.
