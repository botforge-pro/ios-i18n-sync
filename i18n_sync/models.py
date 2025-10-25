"""Data models for i18n-sync."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class TranslationKey(BaseModel):
    """A single translation key with all its language values."""
    translations: Dict[str, str] = Field(default_factory=dict)

    def add_translation(self, lang: str, value: str):
        self.translations[lang] = value

    def get_translation(self, lang: str) -> Optional[str]:
        return self.translations.get(lang)


class StringsSection(BaseModel):
    """A section of strings (e.g., Localizable or InfoPlist)."""
    name: str
    keys: Dict[str, TranslationKey] = Field(default_factory=dict)

    def add_key(self, key: str, lang: str, value: str):
        if key not in self.keys:
            self.keys[key] = TranslationKey()
        self.keys[key].add_translation(lang, value)

    def get_languages(self) -> set[str]:
        """Get all languages used in this section."""
        languages = set()
        for key in self.keys.values():
            languages.update(key.translations.keys())
        return languages


class TranslationsData(BaseModel):
    """The complete translations data structure."""
    sections: Dict[str, StringsSection] = Field(default_factory=dict)

    def add_section(self, name: str) -> StringsSection:
        if name not in self.sections:
            self.sections[name] = StringsSection(name=name)
        return self.sections[name]

    def get_all_languages(self) -> set[str]:
        """Get all languages across all sections."""
        languages = set()
        for section in self.sections.values():
            languages.update(section.get_languages())
        return languages

    def to_yaml_dict(self) -> Dict:
        """Convert to a dict suitable for YAML serialization."""
        result = {}
        for section_name, section in self.sections.items():
            result[section_name] = {}
            for key, trans_key in section.keys.items():
                # Sort languages with 'en' first if it exists
                sorted_langs = {}
                if 'en' in trans_key.translations:
                    sorted_langs['en'] = trans_key.translations['en']
                for lang in sorted(trans_key.translations.keys()):
                    if lang != 'en':
                        sorted_langs[lang] = trans_key.translations[lang]
                result[section_name][key] = sorted_langs
        return result

    @classmethod
    def from_yaml_dict(cls, data: Dict) -> "TranslationsData":
        """Create from a dict loaded from YAML."""
        trans_data = cls()
        for section_name, section_data in data.items():
            section = trans_data.add_section(section_name)
            for key, translations in section_data.items():
                for lang, value in translations.items():
                    section.add_key(key, lang, value)
        return trans_data