# Changelog

All notable release changes are recorded here. Deployments that predate the
versioned release process are not reconstructed as releases.

## [Unreleased]

## [0.1.0] - 2026-09-11 09:40 UTC

- Added canonical `event_translations` storage and a bounded, verifiable legacy-summary backfill command.
- Moved private event readers and writers to translation rows while retaining legacy summary columns for rollback.
- Added the compatible public `event_type` projection and exposed category/type labels in the public web application.
- Preserved both Traditional Chinese and English summaries during the rehearsed R4 database rollback.

