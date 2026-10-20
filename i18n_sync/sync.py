"""Main synchronization class for iOS i18n."""

import plistlib
import re
from collections.abc import Iterator
from pathlib import Path

import yaml

from .catalog import (
    Catalog,
    fill_plural_variable,
    plural_variable,
    plural_variables,
    widen_integer_specifiers,
)
from .models import TranslationsData

CATALOG_SECTION = "Localizable"
# A .strings header is the comments it opens with, however its keys are laid out.
LEADING_COMMENTS = re.compile(r"(?:\s*(?:/\*.*?\*/|//[^\n]*))*", re.DOTALL)
# An Android resource qualifier naming a locale: ru, pt-rBR, b+zh+Hant+TW. Of the
# other qualifiers only the UI mode `car` has that shape: the rest are longer or
# carry digits (https://developer.android.com/guide/topics/resources/providing-resources#AlternativeResources).
NOT_A_LOCALE = {"car"}
LOCALE_QUALIFIER = re.compile(
    r"[a-z]{2,3}(?:-r[A-Z]{2})?|b\+[a-z]{2,3}(?:\+[A-Za-z0-9]+)*"
)

# iOS to Android language code mapping
# Full list for all App Store supported locales
# See: https://developer.apple.com/help/app-store-connect/reference/app-store-localizations/
IOS_TO_ANDROID_LANG = {
    # Chinese variants (use region format for locales_config.xml compatibility)
    "zh-Hans": "zh-rCN",  # Chinese Simplified
    "zh-Hant": "zh-rTW",  # Chinese Traditional
    "zh-Hant-TW": "b+zh+Hant+TW",  # Chinese Traditional (Taiwan)
    "zh-HK": "zh-rHK",  # Chinese Hong Kong
    # Portuguese variants
    "pt-BR": "pt-rBR",  # Portuguese Brazil
    "pt-PT": "pt-rPT",  # Portuguese Portugal
    # Spanish variants
    "es-419": "b+es+419",  # Spanish Latin America
    "es-MX": "es-rMX",  # Spanish Mexico
    # English variants
    "en-AU": "en-rAU",  # English Australia
    "en-CA": "en-rCA",  # English Canada
    "en-GB": "en-rGB",  # English United Kingdom
    "en-US": "en-rUS",  # English United States
    # French variants
    "fr-CA": "fr-rCA",  # French Canada
    # Serbian variants
    "sr-Latn": "b+sr+Latn",  # Serbian Latin
    "sr-Latn-ME": "b+sr+Latn+ME",  # Serbian Latin Montenegro
    # Norwegian (iOS uses 'nb' for Bokmål, Android accepts both)
    # "nb" stays "nb" - no mapping needed
    # Hebrew (iOS may use 'he', Android uses 'iw')
    "he": "iw",
    # Indonesian (iOS may use 'id', Android historically used 'in')
    # Modern Android accepts 'id', but 'in' for compatibility
    # "id": "in",  # Uncomment if targeting old Android versions
    # Yiddish
    "yi": "ji",
}


class I18nSync:
    """Synchronize iOS .strings files through YAML with sections."""

    def __init__(
        self,
        resources_path: str = "Resources",
        yaml_path: str = "translations.yaml",
        source_lang: str = "en",
    ):
        """
        Initialize the sync tool.

        Args:
            resources_path: Path to Resources directory containing *.lproj folders
            yaml_path: Path to the YAML file for translations
            source_lang: The source language that defines the canonical key list
        """
        self.resources_path = Path(resources_path)
        self.yaml_path = Path(yaml_path)
        self.source_lang = source_lang
        self.strings_files = ["Localizable", "InfoPlist", "AppShortcuts"]
        self.translations = TranslationsData()
        self.plurals = {}  # {key: {lang: {quantity: value}}}
        self.unread_stringsdict_entries = []

    @property
    def catalog_path(self) -> Path:
        return self.resources_path / f"{CATALOG_SECTION}.xcstrings"

    def extract(self) -> None:
        """Extract all translations to YAML.

        Localizable strings come from Localizable.xcstrings when the project has a
        String Catalog, otherwise from the .strings and .stringsdict files.
        """
        self._read_resources()
        self._save_yaml()
        self._report_statistics()

    def convert_to_catalog(self) -> None:
        """Move Localizable.strings and .stringsdict of every language into one catalog.

        %d becomes %lld, which Xcode's generated symbols take as Int.
        InfoPlist and AppShortcuts strings stay where they are.
        """
        if self.catalog_path.exists():
            raise FileExistsError(f"{self.catalog_path} already exists")
        self._read_resources()
        if self.unread_stringsdict_entries:
            raise ValueError(
                "These .stringsdict entries are not a plural this tool reads, and "
                "converting would lose them with the file: "
                f"{', '.join(self.unread_stringsdict_entries)}. Move each into "
                "Localizable.strings or rewrite it as a plural, then convert again."
            )
        section = self.translations.sections.get(CATALOG_SECTION)
        strings = {
            key: {
                lang: widen_integer_specifiers(value)
                for lang, value in trans_key.translations.items()
            }
            for key, trans_key in (section.keys.items() if section else [])
        }
        plurals = {
            key: {
                lang: {
                    name: widen_integer_specifiers(value)
                    for name, value in forms.items()
                }
                for lang, forms in langs.items()
            }
            for key, langs in self.plurals.items()
        }
        catalog = Catalog(self.catalog_path)
        catalog.data["sourceLanguage"] = self.source_lang
        catalog.write(strings, plurals, self._yaml_languages())
        for lproj_dir in self._get_lproj_directories():
            for suffix in (".strings", ".stringsdict"):
                old = lproj_dir / f"{CATALOG_SECTION}{suffix}"
                if old.exists():
                    old.unlink()
                    print(f"Removed {old}")
            if not any(lproj_dir.iterdir()):
                lproj_dir.rmdir()

    def _refuse_strings_beside_the_catalog(self) -> None:
        if not self.catalog_path.exists():
            return
        leftovers = [
            path
            for suffix in (".strings", ".stringsdict")
            for path in sorted(
                self.resources_path.glob(f"*.lproj/{CATALOG_SECTION}{suffix}")
            )
        ]
        if leftovers:
            raise ValueError(
                f"{self.catalog_path} holds the {CATALOG_SECTION} strings, but these files "
                f"still do too: {', '.join(str(path) for path in leftovers)}. "
                "Xcode would build both; remove them or the catalog."
            )

    def _read_resources(self) -> None:
        self.translations = TranslationsData()
        self.plurals = {}
        self.unread_stringsdict_entries = []

        self._refuse_strings_beside_the_catalog()
        if self.catalog_path.exists():
            self._read_catalog()
        for lproj_dir in self._lproj_directories_if_needed():
            self._process_language_directory(lproj_dir)

        self._drop_keys_missing_from_source_lang()

    def _read_catalog(self) -> None:
        strings, plurals = Catalog(self.catalog_path).read()
        section = self.translations.add_section(CATALOG_SECTION)
        for key, values in strings.items():
            for lang, value in values.items():
                section.add_key(key, lang, value)
        self.plurals.update(plurals)

    def _lproj_directories_if_needed(self):
        if self.catalog_path.exists():
            return list(self.resources_path.glob("*.lproj"))
        return self._get_lproj_directories()

    def _get_lproj_directories(self):
        lproj_dirs = list(self.resources_path.glob("*.lproj"))
        if not lproj_dirs:
            raise FileNotFoundError(
                f"No *.lproj directories found in {self.resources_path}"
            )
        return lproj_dirs

    def _process_language_directory(self, lproj_dir: Path) -> None:
        lang = lproj_dir.stem

        for strings_file_name in self.strings_files:
            if strings_file_name == CATALOG_SECTION and self.catalog_path.exists():
                continue
            strings_file = lproj_dir / f"{strings_file_name}.strings"
            if strings_file.exists():
                self._parse_strings_file(strings_file, lang, strings_file_name)

            # Also check for stringsdict (plurals)
            stringsdict_file = lproj_dir / f"{strings_file_name}.stringsdict"
            if stringsdict_file.exists():
                self._parse_stringsdict_file(stringsdict_file, lang)

    def _drop_keys_missing_from_source_lang(self) -> None:
        """Remove keys that don't exist in the source language.

        The source language defines the canonical key list. Keys present in
        other languages but missing from the source language are considered
        deleted and are dropped from the extraction result.
        """
        for section in self.translations.sections.values():
            dead_keys = [
                key
                for key, trans_key in section.keys.items()
                if trans_key.get_translation(self.source_lang) is None
            ]
            for key in dead_keys:
                del section.keys[key]

    def apply(self) -> None:
        """Apply translations from YAML to .strings and .stringsdict files."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")

        self._load_yaml()
        languages = self._yaml_languages()

        self._refuse_strings_beside_the_catalog()
        missing = 0
        removed = set()
        uses_catalog = self.catalog_path.exists()
        for section_name in self.strings_files:
            if section_name == CATALOG_SECTION and uses_catalog:
                catalog = Catalog(self.catalog_path)
                missing += self._apply_catalog(catalog)
                removed |= catalog.removed_languages
            else:
                missing += self._apply_section(section_name, languages)

        # Write .stringsdict files for plurals
        if self.plurals and not uses_catalog:
            self._apply_stringsdict(languages)

        if languages:
            removed |= self._remove_languages_left_out(languages)
        for lang in sorted(removed):
            print(f"Remove {lang} from the localizations of the Xcode project too")

        print(f"Applied translations to {len(languages)} languages")
        if missing:
            # A per-key warning scrolls past in a wall of "Updated ..." lines.
            # The count is what a human actually reads.
            print(f"{missing} missing translation(s) written as empty strings")

    def _yaml_languages(self) -> set[str]:
        languages = self.translations.get_all_languages()
        for lang_data in self.plurals.values():
            languages.update(k for k in lang_data if k != "_format_key")
        return languages

    def _remove_languages_left_out(self, languages: set[str]) -> set[str]:
        """Delete the files this tool writes for a language the YAML no longer has.

        Left in place, they would still ship, and the next extract would read the
        language back. Other files in the .lproj, such as storyboards, stay.
        Returns the languages that lost a file.
        """
        removed = set()
        for lproj_dir in self.resources_path.glob("*.lproj"):
            if lproj_dir.stem in languages:
                continue
            for name in self.strings_files:
                for suffix in (".strings", ".stringsdict"):
                    written = lproj_dir / f"{name}{suffix}"
                    if written.exists():
                        written.unlink()
                        removed.add(lproj_dir.stem)
                        print(f"Removed {written}")
            if not any(lproj_dir.iterdir()):
                lproj_dir.rmdir()
        return removed

    # ==================== Editing the YAML ====================

    def remove_languages(self, languages: list[str]) -> None:
        """Drop languages from every key and plural of the YAML."""
        self._load_existing_yaml()
        if self.source_lang in languages:
            raise ValueError(
                f"{self.source_lang} is the source language and defines the keys"
            )
        self._require_languages(languages)
        for translations in self._all_translations():
            for lang in languages:
                translations.pop(lang, None)
        self._save_yaml()

    def rename_language(self, old: str, new: str) -> None:
        """Move every translation of one language code to another."""
        self._load_existing_yaml()
        if old == self.source_lang:
            raise ValueError(f"{old} is the source language and defines the keys")
        self._require_languages([old])
        if new in self._yaml_languages():
            raise ValueError(f"{new} already has translations")
        for translations in self._all_translations():
            if old in translations:
                translations[new] = translations.pop(old)
        self._save_yaml()

    def remove_keys(self, keys: list[str]) -> None:
        """Drop keys from every section and from the plurals."""
        self._load_existing_yaml()
        sections = [section.keys for section in self.translations.sections.values()]
        unknown = [
            key
            for key in keys
            if key not in self.plurals and not any(key in found for found in sections)
        ]
        if unknown:
            raise ValueError(f"No such key: {', '.join(unknown)}")
        for key in keys:
            self.plurals.pop(key, None)
            for found in sections:
                found.pop(key, None)
        self._save_yaml()

    def _load_existing_yaml(self) -> None:
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")
        self._load_yaml()

    def _require_languages(self, languages: list[str]) -> None:
        present = self._yaml_languages()
        unknown = [lang for lang in languages if lang not in present]
        if unknown:
            raise ValueError(f"No translations in {', '.join(unknown)}")

    def _all_translations(self) -> Iterator[dict]:
        for section in self.translations.sections.values():
            for trans_key in section.keys.values():
                yield trans_key.translations
        yield from self.plurals.values()

    def _apply_catalog(self, catalog: Catalog) -> int:
        section = self.translations.sections.get(CATALOG_SECTION)
        strings = {
            key: dict(trans_key.translations)
            for key, trans_key in (section.keys.items() if section else [])
        }
        if not strings and not self.plurals:
            print(
                f"{self.yaml_path} has no {CATALOG_SECTION} strings: "
                f"{self.catalog_path} is left as it is"
            )
            return 0
        return catalog.write(strings, self.plurals, self._yaml_languages())

    def _apply_section(self, section_name: str, languages: set[str]) -> int:
        section = self.translations.sections.get(section_name)
        if not section:
            return 0

        return sum(self._write_section_to_language(section, lang) for lang in languages)

    def _write_section_to_language(self, section, lang: str) -> int:
        lproj_dir = self.resources_path / f"{lang}.lproj"
        lproj_dir.mkdir(exist_ok=True, parents=True)

        strings_file = lproj_dir / f"{section.name}.strings"
        return self._write_strings_file(strings_file, lang, section)

    def _apply_stringsdict(self, languages: set[str]) -> None:
        """Write plurals from YAML to .stringsdict files for each language."""
        for lang in languages:
            # Collect all plural keys that have this language
            lang_plurals = {}
            for key, lang_data in self.plurals.items():
                if lang in lang_data:
                    forms = lang_data[lang]
                    # Inherit key-level _format_key if language doesn't have its own
                    if "_format_key" not in forms and "_format_key" in lang_data:
                        forms = {**forms, "_format_key": lang_data["_format_key"]}
                    lang_plurals[key] = forms

            if not lang_plurals:
                continue

            lproj_dir = self.resources_path / f"{lang}.lproj"
            lproj_dir.mkdir(exist_ok=True, parents=True)

            stringsdict_file = lproj_dir / "Localizable.stringsdict"
            self._write_stringsdict_file(stringsdict_file, lang_plurals)

    def _write_stringsdict_file(self, file_path: Path, lang_plurals: dict) -> None:
        """Write or merge plurals into an iOS .stringsdict plist file."""
        # Load existing plist to preserve keys not in YAML
        existing = {}
        if file_path.exists():
            with open(file_path, "rb") as f:
                existing = plistlib.load(f)

        # Merge new plurals into existing
        for key, forms in lang_plurals.items():
            format_key_value = forms.get("_format_key")

            # Determine variable name and format key
            if format_key_value:
                var_name = plural_variable(format_key_value) or "count"
            else:
                var_name = "count"
                format_key_value = f"%#@{var_name}@"

            # Build plural dict
            plural_dict = {
                "NSStringFormatSpecTypeKey": "NSStringPluralRuleType",
                "NSStringFormatValueTypeKey": "d",
            }
            for quantity in ["zero", "one", "two", "few", "many", "other"]:
                if quantity in forms:
                    plural_dict[quantity] = forms[quantity]

            existing[key] = {
                "NSStringLocalizedFormatKey": format_key_value,
                var_name: plural_dict,
            }

        # Write plist
        with open(file_path, "wb") as f:
            plistlib.dump(existing, f, fmt=plistlib.FMT_XML)

        print(f"Updated {file_path}")

    def _parse_strings_file(
        self, file_path: Path, lang: str, section_name: str
    ) -> None:
        content = file_path.read_text(encoding="utf-8")
        section = self.translations.add_section(section_name)

        pattern = r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)";\s*(?://.*)?'
        for match in re.finditer(pattern, content):
            key = self._unescape_strings_value(match.group(1))
            value_raw = match.group(2)
            value = self._unescape_strings_value(value_raw)
            section.add_key(key, lang, value)

    def _parse_stringsdict_file(self, file_path: Path, lang: str) -> None:
        """Parse iOS .stringsdict file and extract plurals."""
        with open(file_path, "rb") as f:
            plist = plistlib.load(f)

        # Each key in plist is a plural key
        for key, entry in plist.items():
            plural_forms = self._single_plural(entry)
            if plural_forms is None:
                self.unread_stringsdict_entries.append(f"{file_path}: {key}")
                continue
            format_key = entry["NSStringLocalizedFormatKey"]
            # Save _format_key inside plural_forms if it's more than just the placeholder
            # e.g., "Only %#@texts@ available..." vs just "%#@texts@"
            if format_key != f"%#@{plural_variable(format_key)}@":
                plural_forms["_format_key"] = format_key
            self.plurals.setdefault(key, {})[lang] = plural_forms

    def _single_plural(self, entry) -> dict | None:
        """The forms of an entry that substitutes exactly one plural, else None.

        Anything else — no substitution, several, one of another rule type, or a
        plural without forms — is beyond what the YAML and the catalog carry.
        """
        if not isinstance(entry, dict):
            return None
        names = plural_variables(entry.get("NSStringLocalizedFormatKey", ""))
        if len(names) != 1:
            return None
        rule = entry.get(names[0])
        if not isinstance(rule, dict):
            return None
        if rule.get("NSStringFormatSpecTypeKey") != "NSStringPluralRuleType":
            return None
        forms = {
            quantity: rule[quantity]
            for quantity in ["zero", "one", "two", "few", "many", "other"]
            if quantity in rule
        }
        return forms or None

    def _unescape_strings_value(self, value: str) -> str:
        return value.replace('\\"', '"').replace("\\\\", "\\")

    def _escape_strings_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _write_strings_file(self, file_path: Path, lang: str, section) -> int:
        """Write translations to a .strings file, returning the missing count."""
        missing = 0
        # Get header if file exists
        header = self._get_file_header(file_path, lang, section.name)

        # Build content
        lines = []
        if header:
            lines.append(header)

        # Write keys sorted alphabetically
        for key in sorted(section.keys.keys()):
            trans_key = section.keys[key]
            value = trans_key.get_translation(lang)
            escaped_key = self._escape_strings_value(key)
            # An empty value is NOT a translation. iOS treats `"key" = "";` as a
            # valid string and does not fall back to Base, so the label renders
            # blank. Absent and empty therefore have to be reported the same way.
            if value is not None and value.strip():
                escaped_value = self._escape_strings_value(value)
                lines.append(f'"{escaped_key}" = "{escaped_value}";')
            else:
                # Add empty value for missing translation
                lines.append(f'"{escaped_key}" = "";')
                missing += 1
                print(f"Warning: Missing '{section.name}.{key}' for language '{lang}'")

        # Write file
        content = "\n".join(lines)
        if content and not content.endswith("\n"):
            content += "\n"

        file_path.write_text(content, encoding="utf-8")
        print(f"Updated {file_path}")
        return missing

    def _get_file_header(
        self, file_path: Path, lang: str, file_type: str
    ) -> str | None:
        """Keep an existing file's header, or its lack of one; a new file gets the default."""
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8").lstrip("﻿")
            header = LEADING_COMMENTS.match(content).group(0).strip()
            return header or None

        # Default header with better language names
        lang_names = {
            "en": "English",
            "es": "Spanish",
            "es-419": "Spanish (Latin America)",
            "es-MX": "Spanish (Mexico)",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "nl": "Dutch",
            "pt-PT": "Portuguese (Portugal)",
            "pt-BR": "Portuguese (Brazil)",
            "sv": "Swedish",
            "nb": "Norwegian Bokmål",
            "da": "Danish",
            "fi": "Finnish",
            "pl": "Polish",
            "el": "Greek",
            "ru": "Russian",
            "uk": "Ukrainian",
            "sr": "Serbian (Cyrillic)",
            "sr-Latn": "Serbian (Latin)",
            "tr": "Turkish",
            "th": "Thai",
            "vi": "Vietnamese",
            "id": "Indonesian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh-Hans": "Chinese (Simplified)",
            "zh-Hant": "Chinese (Traditional)",
            "zh-HK": "Chinese (Hong Kong)",
        }

        lang_name = lang_names.get(lang, lang)
        return f"""/*
  {file_type}.strings
  {self._project_name()}

  {lang_name}
*/"""

    def _project_name(self) -> str:
        """Name the app the way Xcode's own header does.

        Taken from the resources path, since that is the only thing the
        tool is told about the project: an app keeps its strings either
        in a Resources folder inside the target, in which case the
        target above it is the name, or in the target folder itself.
        """
        folder = self.resources_path.resolve()
        if folder.name == "Resources":
            return folder.parent.name
        return folder.name

    def _save_yaml(self) -> None:
        """Save translations to YAML file."""
        data = self.translations.to_yaml_dict()

        # Add plurals section if we have any
        if self.plurals:
            plurals_data = {}
            for key in sorted(self.plurals.keys()):
                plurals_data[key] = {}
                langs = self.plurals[key]
                # Sort with 'en' first
                if "en" in langs:
                    plurals_data[key]["en"] = langs["en"]
                for lang in sorted(langs.keys()):
                    if lang != "en":
                        plurals_data[key][lang] = langs[lang]
            data["Plurals"] = plurals_data

        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )

        print(f"Saved translations to {self.yaml_path}")

    def _load_yaml(self) -> None:
        """Load translations from YAML file."""
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Extract plurals section before creating TranslationsData
        self.plurals = data.pop("Plurals", {})

        self.translations = TranslationsData.from_yaml_dict(data)

    def _report_statistics(self) -> None:
        """Report extraction statistics and missing keys."""
        total_keys = 0
        languages = self.translations.get_all_languages()

        for entry in self.unread_stringsdict_entries:
            print(f"Warning: not a plural this tool reads, left out: {entry}")
        print("\nExtraction summary:")
        for section_name, section in self.translations.sections.items():
            key_count = len(section.keys)
            total_keys += key_count
            print(f"  {section_name}: {key_count} keys")

        print(f"\nTotal: {total_keys} keys from {len(languages)} languages")

        # Check for missing translations
        missing_found = False
        for section_name, section in self.translations.sections.items():
            for key, trans_key in section.keys.items():
                missing_langs = {
                    lang
                    for lang in languages
                    if not (trans_key.get_translation(lang) or "").strip()
                }
                if missing_langs:
                    if not missing_found:
                        print("\nMissing translations:")
                        missing_found = True
                    print(
                        f"  {section_name}.{key}: missing in {', '.join(sorted(missing_langs))}"
                    )

        if not missing_found:
            print("\nAll keys present in all languages ✓")

    # ==================== Android support ====================

    def apply_android(
        self, res_path: str = "app/src/main/res", default_lang: str = "en"
    ) -> None:
        """Apply translations from YAML to Android strings.xml files."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")

        self._load_yaml()
        res_path = Path(res_path)

        # Get all languages from both strings and plurals
        languages = set()
        for section_name, section in self.translations.sections.items():
            if section_name != "AppShortcuts":
                languages.update(section.get_languages())
        for lang_data in self.plurals.values():
            languages.update(lang for lang in lang_data if lang != "_format_key")

        for lang in languages:
            self._write_android_strings(res_path, lang, default_lang)
        if languages:
            self._remove_android_languages_left_out(
                res_path,
                {self._android_folder(lang, default_lang) for lang in languages},
            )

        # Generate locales_config.xml for per-app language support
        self._write_locales_config(res_path, languages)

        print(f"Applied translations to {len(languages)} Android languages")

    def _write_android_strings(
        self, res_path: Path, lang: str, default_lang: str
    ) -> None:
        """Write strings.xml for a specific language."""
        values_dir = res_path / self._android_folder(lang, default_lang)
        values_dir.mkdir(parents=True, exist_ok=True)

        strings_file = values_dir / "strings.xml"
        self._write_android_xml(strings_file, lang)

    def _android_folder(self, lang: str, default_lang: str) -> str:
        if lang == default_lang:
            return "values"
        return f"values-{IOS_TO_ANDROID_LANG.get(lang, lang)}"

    def _remove_android_languages_left_out(
        self, res_path: Path, written: set[str]
    ) -> None:
        """Delete strings.xml of a language the YAML no longer has.

        Only a folder whose qualifier is a locale counts: values-night, values-car
        or values-v21 keep their strings.xml.
        """
        for values_dir in res_path.glob("values-*"):
            strings_file = values_dir / "strings.xml"
            qualifier = values_dir.name.removeprefix("values-")
            if (
                values_dir.name in written
                or qualifier in NOT_A_LOCALE
                or not LOCALE_QUALIFIER.fullmatch(qualifier)
            ):
                continue
            if strings_file.exists():
                strings_file.unlink()
                print(f"Removed {strings_file}")
            if not any(values_dir.iterdir()):
                values_dir.rmdir()

    def _write_android_xml(self, file_path: Path, lang: str) -> None:
        """Write Android strings.xml file."""
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]

        # Collect all keys from all sections for this language
        all_keys = {}
        for section_name, section in self.translations.sections.items():
            if section_name == "AppShortcuts":
                continue
            for key, trans_key in section.keys.items():
                value = trans_key.get_translation(lang)
                if value is not None:
                    all_keys[key] = value

        # Write string keys sorted alphabetically
        for key in sorted(all_keys.keys()):
            value = all_keys[key]
            escaped_value = self._escape_android_xml(value)
            lines.append(f'    <string name="{key}">{escaped_value}</string>')

        # Write plurals for this language
        for plural_key in sorted(self.plurals.keys()):
            lang_data = self.plurals[plural_key]
            if lang in lang_data:
                forms = lang_data[lang]
                format_key = forms.get("_format_key")
                lines.append(f'    <plurals name="{plural_key}">')
                # Android quantity order: zero, one, two, few, many, other
                for quantity in ["zero", "one", "two", "few", "many", "other"]:
                    if quantity in forms:
                        plural_value = forms[quantity]
                        # If _format_key exists, substitute the plural form into it
                        if format_key:
                            full_value = fill_plural_variable(format_key, plural_value)
                        else:
                            full_value = plural_value
                        escaped_value = self._escape_android_xml(full_value)
                        lines.append(
                            f'        <item quantity="{quantity}">{escaped_value}</item>'
                        )
                lines.append("    </plurals>")

        lines.append("</resources>")

        content = "\n".join(lines) + "\n"
        file_path.write_text(content, encoding="utf-8")
        print(f"Updated {file_path}")

    def _escape_android_xml(self, value: str) -> str:
        """Escape special characters for Android XML."""
        # Convert iOS format specifiers to Android
        value = self._convert_format_specifiers(value)
        # Order matters: ampersand first
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        value = value.replace("'", "\\'")
        value = value.replace('"', '\\"')
        return value

    def _convert_format_specifiers(self, value: str) -> str:
        """Convert iOS format specifiers to Android format.

        - %@ -> %s (iOS object placeholder to Android string)
        - Multiple specifiers get positional args: %d %d -> %1$d %2$d
        - Already positional specifiers: %1$@ -> %1$s (convert type only)
        """
        # An escaped "%%" is matched first and kept, so "%%d" stays a percent sign
        # and a letter rather than becoming an argument.
        pattern = re.compile(
            r"%%|%(\d+\$)?(\.\d+)?(@|l{0,2}[diu]|[fxXoOeEgGsScCpPaAbBhHnN])"
        )
        unnumbered = sum(
            1 for m in pattern.finditer(value) if m.group(0) != "%%" and not m.group(1)
        )
        position = 0

        def convert(match: re.Match) -> str:
            nonlocal position
            if match.group(0) == "%%":
                return "%%"
            precision = match.group(2) or ""
            type_spec = self._ios_to_android_type(match.group(3))
            if match.group(1):
                return f"%{match.group(1)}{precision}{type_spec}"
            if unnumbered == 1:
                return f"%{precision}{type_spec}"
            position += 1
            return f"%{position}${precision}{type_spec}"

        return pattern.sub(convert, value)

    def _ios_to_android_type(self, ios_type: str) -> str:
        """Convert iOS type specifier to Android."""
        if ios_type == "@":
            return "s"
        return ios_type.lstrip("l")

    def _write_locales_config(self, res_path: Path, languages: set[str]) -> None:
        """Generate locales_config.xml for Android per-app language support."""
        xml_dir = res_path / "xml"
        xml_dir.mkdir(parents=True, exist_ok=True)

        config_file = xml_dir / "locales_config.xml"

        # Convert iOS language codes to Android format for locales_config
        android_locales = set()
        for lang in languages:
            android_lang = self._ios_to_android_locale(lang)
            android_locales.add(android_lang)

        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<locale-config xmlns:android="http://schemas.android.com/apk/res/android">',
        ]

        for locale in sorted(android_locales):
            lines.append(f'    <locale android:name="{locale}" />')

        lines.append("</locale-config>")

        content = "\n".join(lines) + "\n"
        config_file.write_text(content, encoding="utf-8")
        print(f"Generated {config_file}")

    def _ios_to_android_locale(self, ios_lang: str) -> str:
        """Convert iOS language code to Android locale format for locales_config.xml.

        Derives from IOS_TO_ANDROID_LANG but converts folder format to locale format:
        - values-zh-rCN -> zh-CN (remove 'r' prefix from region)
        - values-b+sr+Latn -> sr-Latn (BCP 47 to standard format)
        """
        # Get the folder-style mapping first
        folder_code = IOS_TO_ANDROID_LANG.get(ios_lang, ios_lang)

        # Convert folder format to locale format
        if folder_code.startswith("b+"):
            # BCP 47 format: b+sr+Latn -> sr-Latn
            parts = folder_code[2:].split("+")
            return "-".join(parts)
        elif "-r" in folder_code:
            # Region format: zh-rCN -> zh-CN
            return folder_code.replace("-r", "-")
        else:
            return folder_code
