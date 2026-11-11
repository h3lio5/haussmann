# ADR-0002: Database image

Status: accepted, 2026-11-10

Local development and CI use one Postgres 17 image with both PostGIS and pgvector, built from `pgvector/pgvector:pg17` with the Debian `postgresql-17-postgis-3` package added and both extensions created at first start. No published image ships both extensions, and starting from the pgvector image gives multi-architecture builds (arm64 laptops, amd64 CI) with one `apt-get` line; starting from a PostGIS image would mean compiling pgvector. The credentials in `compose.yaml` are for local development only and the port is bound to localhost. Alternatives considered: two databases (splits data that queries join), a managed Postgres for development (cost and network dependence for tests), compiling both extensions from source (slower builds for no gain).
