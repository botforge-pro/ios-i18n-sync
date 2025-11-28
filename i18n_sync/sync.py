"""Main synchronization class for iOS i18n."""

import re
import yaml
from pathlib import Path
from typing import Optional, Set

from .models import TranslationsData


# iOS to Android language code mapping
# Full list for all App Store supported locales
# See: https://developer.apple.com/help/app-store-connect/reference/app-store-localizations/
IOS_TO_ANDROID_LANG = {
    # Chinese variants
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

    def extract(self) -> None:
        """Extract all translations from .strings files to YAML."""
        self.translations = TranslationsData()

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
        languages = self.translations.get_all_languages()

        for lang in languages:
            self._write_android_strings(res_path, lang, default_lang)

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

        # Write keys sorted alphabetically
        for key in sorted(all_keys.keys()):
            value = all_keys[key]
            escaped_value = self._escape_android_xml(value)
            lines.append(f'    <string name="{key}">{escaped_value}</string>')

        lines.append("</resources>")

        content = "\n".join(lines) + "\n"
        file_path.write_text(content, encoding="utf-8")
        print(f"Updated {file_path}")

    def _escape_android_xml(self, value: str) -> str:
        """Escape special characters for Android XML."""
        # Order matters: ampersand first
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        value = value.replace("'", "\\'")
        value = value.replace('"', '\\"')
        return value