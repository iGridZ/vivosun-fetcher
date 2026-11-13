# TASK.md – vivosun-fetcher

Status: 2026-11-13. Updated after every work session.

## Open

### Next up
- [ ] Make the GHCR package public (or `docker login ghcr.io` on the host) so the homelab can pull it
- [ ] Switch the homelab camera stack to `ghcr.io/igridz/vivosun-fetcher:latest`

### Ideas (not decided)
- [ ] Healthcheck (e.g. touch a file after each successful check)
- [ ] Unit tests for `get_camera_credentials` with a recorded API response

## Done

### 2026-11-13 – feature/ci-docker
- [x] Dockerfile: non-root user, no bytecode, minimal context (`.dockerignore`)
- [x] `.env.example`, `.gitignore`, README with sequence diagram
- [x] `compose.yaml` + `scripts/docker-run.sh` (same settings)
- [x] GitHub Actions: lint + build on PRs, `:dev` image from `dev`, `:latest` from `main`
