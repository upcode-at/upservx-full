# Changelog

All notable changes to UpservX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Automatic `/etc/fstab` management when mounting drives via Storage Management UI
- Unmount functionality with automatic fstab cleanup
- UUID-based device identification for stable mounting
- Intelligent mount options based on filesystem type (ext4, ntfs, vfat, exfat, xfs)
- Automatic fstab backup before modifications

### Changed
- Improved fstab formatting with properly aligned columns
- Mount operations now create persistent entries automatically

### Fixed
- Storage mount operations now survive system reboots

---

## [0.1.0] - 2026-02-15

Initial pre-release - see [releases/0.1.0.md](releases/0.1.0.md) for full details.
