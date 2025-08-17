# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- TBD

## [0.1.1] - 2025-08-17
- GitHub Releases now include self-contained tar.gz (Linux/macOS) and zip (Windows) bundles
- Added README-RUN to standalone bundle
- Release workflow refinements

## [0.1.0] - 2025-08-17
- Initial remote multi-user server/client mode (WebSocket + PTY)
- CLI flags: --server/--client/--host/--port, env overrides
- Notes drawer with persistent save path
- Bundled themes and CSS assets packaged
- Packaging: websockets installed by default; wheel includes assets
- Added PyInstaller spec for standalone binaries
- CI release workflow (build wheels and binaries on tag)
