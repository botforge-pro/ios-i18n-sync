"""Main synchronization class for iOS i18n."""

import plistlib
import re
import yaml
from pathlib import Path
from typing import Optional, Set

from .models import TranslationsData


# iOS to Android language code mapping
# Full list for all App Store supported locales
# See: https://developer.apple.com/help/app-store-connect/reference/app-store-localizations/
IOS_TO_ANDROID_LANG = {
    # Chinese variants (use region format for locales_config.xml compatibility)
    "zh-Hans": "zh-rCN",       # Chinese Simplified
    "zh-Hant": "zh-rTW",       # Chinese Traditional
    "zh-HK": "zh-rHK",         # Chinese Hong Kong

    # Portuguese variants
    "pt-BR": "pt-rBR",         # Portuguese Brazil
    "pt-PT": "pt-rPT",         # Portuguese Portugal

    # Spanish variants
    "es-419": "b+es+419",      # Spanish Latin America
    "es-MX": "es-rMX",         # Spanish Mexico

    # English variants
    "en-AU": "en-rAU",         # English Australia
    "en-CA": "en-rCA",         # English Canada
    "en-GB": "en-rGB",         # English United Kingdom
    "en-US": "en-rUS",         # English United States

    # French variants
    "fr-CA": "fr-rCA",         # French Canada

    # Serbian variants
    "sr-Latn": "b+sr+Latn",    # Serbian Latin
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

    def __init__(self, resources_path: str = "Resources", yaml_path: str = "translations.yaml"):
        """
        Initialize the sync tool.

        Args:
            resources_path: Path to Resources directory containing *.lproj folders
            yaml_path: Path to the YAML file for translations
        """
        self.resources_path = Path(resources_path)
        self.yaml_path = Path(yaml_path)
        self.strings_files = ["Localizable", "InfoPlist"]
        self.translations = TranslationsData()
        self.plurals = {}  # {key: {lang: {quantity: value}}}

    def extract(self) -> None:
        """Extract all translations from .strings and .stringsdict files to YAML."""
        self.translations = TranslationsData()
        self.plurals = {}

        for lproj_dir in self._get_lproj_directories():
            self._process_language_directory(lproj_dir)

        self._save_yaml()
        self._report_statistics()

    def _get_lproj_directories(self):
        lproj_dirs = list(self.resources_path.glob("*.lproj"))
        if not lproj_dirs:
            raise FileNotFoundError(f"No *.lproj directories found in {self.resources_path}")
        return lproj_dirs

    def _process_language_directory(self, lproj_dir: Path) -> None:
        lang = lproj_dir.stem

        for strings_file_name in self.strings_files:
            strings_file = lproj_dir / f"{strings_file_name}.strings"
            if strings_file.exists():
                self._parse_strings_file(strings_file, lang, strings_file_name)

            # Also check for stringsdict (plurals)
            stringsdict_file = lproj_dir / f"{strings_file_name}.stringsdict"
            if stringsdict_file.exists():
                self._parse_stringsdict_file(stringsdict_file, lang)

    def apply(self) -> None:
        """Apply translations from YAML to .strings files."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")

        self._load_yaml()
        languages = self.translations.get_all_languages()

        for section_name in self.strings_files:
            self._apply_section(section_name, languages)

        print(f"Applied translations to {len(languages)} languages")

    def _apply_section(self, section_name: str, languages: Set[str]) -> None:
        section = self.translations.sections.get(section_name)
        if not section:
            return

        for lang in languages:
            self._write_section_to_language(section, lang)

    def _write_section_to_language(self, section, lang: str) -> None:
        lproj_dir = self.resources_path / f"{lang}.lproj"
        lproj_dir.mkdir(exist_ok=True, parents=True)

        strings_file = lproj_dir / f"{section.name}.strings"
        self._write_strings_file(strings_file, lang, section)

    def _parse_strings_file(self, file_path: Path, lang: str, section_name: str) -> None:
        content = file_path.read_text(encoding='utf-8')
        section = self.translations.add_section(section_name)

        pattern = r'"([^"]+)"\s*=\s*"((?:[^"\\]|\\.)*)";\s*(?://.*)?'
        for match in re.finditer(pattern, content):
            key = match.group(1)
            value_raw = match.group(2)
            value = self._unescape_strings_value(value_raw)
            section.add_key(key, lang, value)

    def _parse_stringsdict_file(self, file_path: Path, lang: str) -> None:
        """Parse iOS .stringsdict file and extract plurals."""
        with open(file_path, 'rb') as f:
            plist = plistlib.load(f)

        # Each key in plist is a plural key
        for key, entry in plist.items():
            if not isinstance(entry, dict):
                continue

            # Find the plural variable (e.g., "hours" in %#@hours@)
            format_key = entry.get("NSStringLocalizedFormatKey", "")
            # Extract variable name from %#@varname@
            match = re.search(r'%#@(\w+)@', format_key)
            if not match:
                continue

            var_name = match.group(1)
            plural_dict = entry.get(var_name, {})

            if plural_dict.get("NSStringFormatSpecTypeKey") != "NSStringPluralRuleType":
                continue

            # Extract plural forms
            plural_forms = {}
            for quantity in ["zero", "one", "two", "few", "many", "other"]:
                if quantity in plural_dict:
                    plural_forms[quantity] = plural_dict[quantity]

            if plural_forms:
                if key not in self.plurals:
                    self.plurals[key] = {}
                self.plurals[key][lang] = plural_forms

    def _unescape_strings_value(self, value: str) -> str:
        return value.replace('\\"', '"').replace('\\\\', '\\')

    def _escape_strings_value(self, value: str) -> str:
        return value.replace('\\', '\\\\').replace('"', '\\"')

    def _write_strings_file(self, file_path: Path, lang: str, section) -> None:
        """Write translations to a .strings file."""
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
            if value is not None:
                escaped_value = self._escape_strings_value(value)
                lines.append(f'"{key}" = "{escaped_value}";')
            else:
                # Add empty value for missing translation
                lines.append(f'"{key}" = "";')
                print(f"Warning: Missing '{section.name}.{key}' for language '{lang}'")

        # Write file
        content = '\n'.join(lines)
        if content and not content.endswith('\n'):
            content += '\n'

        file_path.write_text(content, encoding='utf-8')
        print(f"Updated {file_path}")

    def _get_file_header(self, file_path: Path, lang: str, file_type: str) -> Optional[str]:
        """Extract header comment from existing file or create default."""
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8')
            # Extract everything before first "key" = "value" line
            match = re.search(r'^"[^"]+"\s*=', content, re.MULTILINE)
            if match:
                header = content[:match.start()].rstrip()
                if header:
                    return header

        # Default header with better language names
        lang_names = {
            'en': 'English',
            'es': 'Spanish',
            'es-419': 'Spanish (Latin America)',
            'es-MX': 'Spanish (Mexico)',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'nl': 'Dutch',
            'pt-PT': 'Portuguese (Portugal)',
            'pt-BR': 'Portuguese (Brazil)',
            'sv': 'Swedish',
            'nb': 'Norwegian Bokmål',
            'da': 'Danish',
            'fi': 'Finnish',
            'pl': 'Polish',
            'el': 'Greek',
            'ru': 'Russian',
            'uk': 'Ukrainian',
            'sr': 'Serbian (Cyrillic)',
            'sr-Latn': 'Serbian (Latin)',
            'tr': 'Turkish',
            'th': 'Thai',
            'vi': 'Vietnamese',
            'id': 'Indonesian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh-Hans': 'Chinese (Simplified)',
            'zh-Hant': 'Chinese (Traditional)',
            'zh-HK': 'Chinese (Hong Kong)'
        }

        lang_name = lang_names.get(lang, lang)
        return f"""/*
  {file_type}.strings
  QRServe

  {lang_name}
*/"""

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
                if 'en' in langs:
                    plurals_data[key]['en'] = langs['en']
                for lang in sorted(langs.keys()):
                    if lang != 'en':
                        plurals_data[key][lang] = langs[lang]
            data["Plurals"] = plurals_data

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f,
                     default_flow_style=False,
                     allow_unicode=True,
                     sort_keys=False,
                     width=120)

        print(f"Saved translations to {self.yaml_path}")

    def _load_yaml(self) -> None:
        """Load translations from YAML file."""
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # Extract plurals section before creating TranslationsData
        self.plurals = data.pop("Plurals", {})

        self.translations = TranslationsData.from_yaml_dict(data)

    def _report_statistics(self) -> None:
        """Report extraction statistics and missing keys."""
        total_keys = 0
        languages = self.translations.get_all_languages()

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
                missing_langs = languages - set(trans_key.translations.keys())
                if missing_langs:
                    if not missing_found:
                        print("\nMissing translations:")
                        missing_found = True
                    print(f"  {section_name}.{key}: missing in {', '.join(sorted(missing_langs))}")

        if not missing_found:
            print("\nAll keys present in all languages ✓")

    # ==================== Android support ====================

    def apply_android(self, res_path: str = "app/src/main/res", default_lang: str = "en") -> None:
        """Apply translations from YAML to Android strings.xml files."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")

        self._load_yaml()
        res_path = Path(res_path)

        # Get all languages from both strings and plurals
        languages = self.translations.get_all_languages()
        for plural_key, lang_data in self.plurals.items():
            languages.update(lang_data.keys())

        for lang in languages:
            self._write_android_strings(res_path, lang, default_lang)

        # Generate locales_config.xml for per-app language support
        self._write_locales_config(res_path, languages)

        print(f"Applied translations to {len(languages)} Android languages")

    def _write_android_strings(self, res_path: Path, lang: str, default_lang: str) -> None:
        """Write strings.xml for a specific language."""
        # Determine folder name
        if lang == default_lang:
            folder_name = "values"
        else:
            android_lang = IOS_TO_ANDROID_LANG.get(lang, lang)
            folder_name = f"values-{android_lang}"

        values_dir = res_path / folder_name
        values_dir.mkdir(parents=True, exist_ok=True)

        strings_file = values_dir / "strings.xml"
        self._write_android_xml(strings_file, lang)

    def _write_android_xml(self, file_path: Path, lang: str) -> None:
        """Write Android strings.xml file."""
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]

        # Collect all keys from all sections for this language
        all_keys = {}
        for section in self.translations.sections.values():
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
                lines.append(f'    <plurals name="{plural_key}">')
                # Android quantity order: zero, one, two, few, many, other
                for quantity in ["zero", "one", "two", "few", "many", "other"]:
                    if quantity in forms:
                        escaped_value = self._escape_android_xml(forms[quantity])
                        lines.append(f'        <item quantity="{quantity}">{escaped_value}</item>')
                lines.append('    </plurals>')

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
        - Already positional specifiers are kept as-is
        """
        # Pattern to match format specifiers (excluding %% which is escaped percent)
        # Matches: %@, %d, %f, %.2f, %ld, etc. but not already positional like %1$d
        pattern = r'%(?!\d+\$)(\.\d+)?(@|[dfiulxXoOeEgGsScCpPaAbBhHnN]|l[diu])'

        # First, find all format specifiers
        matches = list(re.finditer(pattern, value))

        if not matches:
            return value

        # If only one specifier, just convert %@ to %s without positional
        if len(matches) == 1:
            return re.sub(pattern, lambda m: f'%{m.group(1) or ""}{self._ios_to_android_type(m.group(2))}', value)

        # Multiple specifiers: add positional arguments
        result = value
        offset = 0
        for i, match in enumerate(matches, 1):
            start = match.start() + offset
            end = match.end() + offset
            precision = match.group(1) or ""
            type_spec = self._ios_to_android_type(match.group(2))
            replacement = f'%{i}${precision}{type_spec}'
            result = result[:start] + replacement + result[end:]
            offset += len(replacement) - (match.end() - match.start())

        return result

    def _ios_to_android_type(self, ios_type: str) -> str:
        """Convert iOS type specifier to Android."""
        if ios_type == '@':
            return 's'
        return ios_type

    def _write_locales_config(self, res_path: Path, languages: Set[str]) -> None:
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

        lines.append('</locale-config>')

        content = '\n'.join(lines) + '\n'
        config_file.write_text(content, encoding='utf-8')
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