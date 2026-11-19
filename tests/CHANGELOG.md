# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [1.2.0] — unreleased

### Added

- Menu bar sync strip: catalog versions, sync, Discord account menu, avatars via `GET /auth/me`.
- OAuth login/logout (`/auth/openlp`), presentation stats `POST /presentation-events` (with or without login).
- Anonymous `openlp` client id for stats when not logged in.
- JSON/SQLite catalog pull, push on edit, install scripts and release ZIP packaging.

### Changed

- Catalog version display survives failed sync; incremental pull uses stored local version.