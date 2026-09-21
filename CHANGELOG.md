# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-07-03

### Added
- Concurrent multi-engine CLI with `dxfvec convert`, `dxfvec batch`, `dxfvec modify`, `dxfvec enhance`.
- Three vectorization engines: Classic (OpenCV), Advanced (VTracer), Cloud AI (BYOK).
- `--preset` support for laser/CNC workflows.
- `--scale` calibration (pixel to real-world) in `Npx=Nmm` or ratio form.
- QA reporting, DXF audit, native ARC/CIRCLE emission.
- `dxfvec info` runtime diagnostics command.
- `--debug` traceback/config dump on failures.
- Tile-mode LLM vision pipeline (`--provider`, `--crew`).

### Changed
- Minimum Python version raised to 3.10+.
- Default DXF version is R2010.

## [1.0.0] - 2025-01-15

### Added
- Initial release with Classic engine and basic CLI.
- Core OpenCV vectorization pipeline.
