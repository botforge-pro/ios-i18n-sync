# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.2] - 2025-01-11

### Fixed
- Android plurals now correctly use per-language `NSStringLocalizedFormatKey` (each language has its own translated format string)

## [0.7.1] - 2025-01-11

### Fixed
- Android plurals now include full sentence when `NSStringLocalizedFormatKey` contains text around the placeholder (e.g., "Only %#@texts@ available for free..." now correctly generates "Only 10 texts available for free..." instead of just "10 texts")

## [0.7.0] - 2025-01-09

### Added
- Auto-generate `locales_config.xml` for Android per-app language support
- Language codes are automatically converted from iOS to Android locale format

## [0.6.0] - 2025-12-03

### Added
- Parse iOS `.stringsdict` files (plist format) to extract plurals
- Generate Android `<plurals>` XML in strings.xml
- Support all plural forms: zero, one, two, few, many, other
- Plurals stored in separate "Plurals" section in YAML

## [0.5.0] - 2025-11-29

### Added
- Convert iOS format specifiers to Android format (`%@` → `%s`)
- Add positional arguments to format specifiers (`%d` → `%1$d`)

## [0.4.0] - 2025-11-28

### Added
- `apply-android` command to generate Android `strings.xml` from YAML
- iOS to Android language code mapping (e.g., `zh-Hans` → `zh-rCN`)

## [0.3.2] - 2025-11-09

### Fixed
- Fix parsing of escaped quotes in .strings files

## [0.3.1] - 2025-11-09

### Fixed
- Fix quote escaping in .strings files

### Changed
- Drop Python 3.8 support (EOL)

## [0.3.0] - 2025-10-25

### Changed
- Sectioned YAML format with Pydantic models for Localizable and InfoPlist strings
- Add Dependabot for Python dependencies

## [0.2.0] - 2025-08-26

### Added
- Support for custom strings files (e.g., `InfoPlist.strings`)

## [0.1.0] - 2025-08-24

### Added
- Initial release
- Extract `.strings` files to YAML
- Apply YAML back to `.strings` files
- GitHub Actions for tests

[0.7.2]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/botforge-pro/ios-i18n-sync/releases/tag/v0.1.0
