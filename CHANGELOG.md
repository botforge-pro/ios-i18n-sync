# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.0] - 2026-10-20

### Added
- `remove-language tr ar`, `rename-language es-MX es` and `remove-key old_title` rewrite `translations.yaml` in place (`--input` picks another file), in every section and in the plurals. Run them between `extract` and `apply`. They never guess: removing or renaming the source language (`--source-lang`, `en` by default), a language or key the file does not have, and a rename onto a language some key already has all end with an error and exit code 1, leaving the file untouched.

### Changed
- `apply` now deletes files. For each `<lang>.lproj` whose language is in no key of the YAML, it deletes the `Localizable`, `InfoPlist` and `AppShortcuts` `.strings` and `.stringsdict` files, then the `.lproj` itself if it is left empty; a storyboard or any other file keeps it. Before, these files stayed: the language still shipped in the app, and the next `extract` put it back into the YAML.
- With a String Catalog, `apply` takes such a language out of `Localizable.xcstrings` entirely, including its variations by device and strings with several substitutions, which the YAML cannot hold. A language the catalog has only in those forms was never in the YAML and is kept. The source language is never taken out.
- `apply` prints `Remove <lang> from the localizations of the Xcode project too` for each language it took out. It does not edit the `.xcodeproj`; remove the language under Project → Info → Localizations by hand.
- `apply-android` deletes `strings.xml` from each `values-<locale>` folder whose language is in no key of the YAML, then the folder if it is left empty. A folder counts as a locale only in the forms the tool writes, such as `values-ru`, `values-pt-rBR` and `values-b+zh+Hant+TW`; `values-night`, `values-car`, `values-v21` and combined qualifiers are left alone.
- Neither command deletes anything when the YAML has no language at all. A language is matched by its exact code, so `es` in the YAML does not keep `es-MX`, and `Base` is a language like any other: `extract` puts it in the YAML, and it is kept while it is there. `locales_config.xml` is rewritten as before and lists only the languages the YAML has.

### Fixed
- `apply` with a YAML that has neither Localizable strings nor plurals, such as one holding only InfoPlist strings, emptied `Localizable.xcstrings`. It now leaves the catalog as it is and prints that it did.

### Upgrading
- Commit before the first `apply` or `apply-android` with 0.14.0 and read the diff: files of a language that is on disk but missing from the YAML, whether a leftover or one the YAML lost by mistake, are deleted on that run.

## [0.13.3] - 2026-10-12

### Fixed
- `convert-to-catalog` skipped a `.stringsdict` entry it could not carry and then deleted the file it lived in: a bare `NSStringLocalizedFormatKey`, a format with several substitutions (only the first was kept), a substitution of another rule type, a plural without forms, an entry that is not a dictionary. It now refuses and names every such entry, leaving the files as they are; `extract` warns about them.

## [0.13.2] - 2026-10-12

### Fixed
- `apply` put a default header comment on top of an existing `.strings` file that had none, so a project without headers had to cut it off after every run. A file keeps its header, or its lack of one; only a new file gets the default.

## [0.13.1] - 2026-10-12

### Fixed
- `convert-to-catalog` and `apply` took an escaped percent followed by a space and `d`, `i` or `u` for a format specifier, so `"%d%% de réduction"` became `"%lld%% llde réduction"`. A catalog converted by 0.13.0 is worth searching for `%% ll`.
- A `%%` before a plural's `%#@count@` no longer shifts the substitution's argument number, and `%%#@name@` is no longer taken for the plural's placeholder.
- Reading a `.stringsdict` took `%%#@name@` for the plural's placeholder, so `convert-to-catalog` dropped such a key and then deleted the file it came from; writing one and `apply-android` made the same mistake.
- `apply-android` left a numbered plural placeholder such as `%2$#@count@` in the string; the form now takes its place and its number, `%1$s has %2$d files`.
- `extract` read a literal `%%arg` in a plural form as the number, so the next `apply` lost it.
- `apply-android` numbered an escaped `%%d` as an argument: `"%lld files, %%d"` became `"%1$d files, %%2$d"`.

## [0.13.0] - 2026-10-12

### Added
- String Catalog support. With `Localizable.xcstrings` in the resources folder, `extract` and `apply` work on it instead of the per-language `Localizable.strings` and `.stringsdict`. Comments and localizations the YAML cannot express (variations by device, several substitutions in one string) are kept as they are; a missing translation is left out so the source language shows.
- `convert-to-catalog` moves a project's Localizable strings and plurals into the catalog, widening `%d`, `%i` and `%u` to their `ll` forms so Xcode's generated symbols take `Int`.

### Fixed
- `apply-android` turned `%ld` and `%lld` into specifiers Java's formatter rejects; they now become `%d`.

## [0.12.0] - 2026-10-12

### Added
- `swiftgen/strings.stencil`: SwiftGen's `structured-swift5` strings template with `L10n` declared `nonisolated`, so a Swift 6 target with the main actor as default isolation can read its strings off the main actor.

## [0.11.0] - 2026-09-04

### Added
- `extract` and `apply` now carry `AppShortcuts.strings` through the same YAML source as `Localizable.strings` and `InfoPlist.strings`.
- `apply-android` ignores the Apple-only shortcut phrases instead of treating them as Android resource keys.

### Changed
- Python 3.10 is now the minimum supported version.

## [0.10.2] - 2026-08-25

### Fixed
- The header of a newly created locale file names the project the strings belong to, taken from the resources path. It was hardcoded to the name of the app the tool was first written for, so every other project got locale files declaring themselves part of that app.

## [0.10.1] - 2026-08-05

### Fixed
- An empty value is now reported as a missing translation, by both `extract` and `apply`. iOS treats `"key" = "";` as a valid string and does not fall back to Base, so a blank entry renders as a blank label; reporting it as present was a false green. One app shipped with 84 of its 130 Croatian strings empty and neither command said anything.
- `apply` prints a total after the per-key warnings, which otherwise scroll past in a wall of `Updated ...` lines.
- Whitespace-only values count as empty.

## [0.10.0] - 2026-03-25

### Added
- Support for positional plural variables (`%2$#@var@`) in stringsdict parsing and writing
- Support for key-level `_format_key` in YAML (shared across all languages, not duplicated per-language)
- Key-level `_format_key` is inherited by languages that don't define their own

## [0.9.1] - 2026-02-25

### Fixed
- Convert `%1$@` to `%1$s` in Android strings (already-positional iOS format specifiers were not being converted)

## [0.9.0] - 2026-02-24

### Added
- `source_lang` parameter (default: `"en"`) to define the canonical key list
- `extract` now drops keys missing from the source language, preventing deleted keys from being re-added via other languages

## [0.8.0] - 2026-02-23

### Added
- `apply` now writes `.stringsdict` files for iOS plurals (previously only `apply-android` handled plurals)
- Merges with existing `.stringsdict` files, preserving keys not in YAML

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

[0.11.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.10.2...v0.11.0
[0.9.1]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/botforge-pro/ios-i18n-sync/compare/v0.7.2...v0.8.0
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
