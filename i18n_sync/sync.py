"""Main synchronization class for iOS i18n."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import OrderedDict


class I18nSync:
    """Synchronize iOS .strings files through YAML."""
    
    def __init__(self, resources_path: str = "Resources", yaml_path: str = "translations.yaml"):
        """
        Initialize the sync tool.
        
        Args:
            resources_path: Path to Resources directory containing *.lproj folders
            yaml_path: Path to the YAML file for translations
        """
        self.resources_path = Path(resources_path)
        self.yaml_path = Path(yaml_path)
        self.translations: Dict[str, Dict[str, str]] = {}
        self.languages: Set[str] = set()
        
    def extract(self) -> None:
        """Extract all translations from .strings files to YAML."""
        self.translations = {}
        self.languages = set()
        
        # Find all .lproj directories
        lproj_dirs = list(self.resources_path.glob("*.lproj"))
        if not lproj_dirs:
            raise FileNotFoundError(f"No *.lproj directories found in {self.resources_path}")
        
        # Process each language
        for lproj_dir in lproj_dirs:
            lang = lproj_dir.stem  # e.g., "en", "ru", "de"
            self.languages.add(lang)
            
            strings_file = lproj_dir / "Localizable.strings"
            if not strings_file.exists():
                print(f"Warning: {strings_file} not found, skipping")
                continue
                
            self._parse_strings_file(strings_file, lang)
        
        # Save to YAML
        self._save_yaml()
        
        # Report statistics
        print(f"Extracted {len(self.translations)} keys from {len(self.languages)} languages")
        self._report_missing_keys()
    
    def apply(self) -> None:
        """Apply translations from YAML to .strings files."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.yaml_path}")
        
        # Load YAML
        self._load_yaml()
        
        # Create/update .strings files for each language
        for lang in self.languages:
            lproj_dir = self.resources_path / f"{lang}.lproj"
            lproj_dir.mkdir(exist_ok=True, parents=True)
            
            strings_file = lproj_dir / "Localizable.strings"
            self._write_strings_file(strings_file, lang)
        
        print(f"Applied {len(self.translations)} keys to {len(self.languages)} languages")
    
    def _parse_strings_file(self, file_path: Path, lang: str) -> None:
        """Parse a .strings file and extract key-value pairs."""
        content = file_path.read_text(encoding='utf-8')
        
        # Regex to match "key" = "value"; pattern
        pattern = r'"([^"]+)"\s*=\s*"([^"]*)";\s*(?://.*)?'
        
        for match in re.finditer(pattern, content):
            key = match.group(1)
            value = match.group(2)
            
            if key not in self.translations:
                self.translations[key] = {}
            
            self.translations[key][lang] = value
    
    def _write_strings_file(self, file_path: Path, lang: str) -> None:
        """Write translations to a .strings file."""
        # Get header if file exists
        header = self._get_file_header(file_path, lang)
        
        # Build content
        lines = [header] if header else []
        
        for key in sorted(self.translations.keys()):
            if lang in self.translations[key]:
                value = self.translations[key][lang]
                lines.append(f'"{key}" = "{value}";')
            else:
                # Add empty value for missing translation
                lines.append(f'"{key}" = "";')
                print(f"Warning: Missing translation for key '{key}' in language '{lang}'")
        
        # Write file
        content = '\n'.join(lines)
        if not content.endswith('\n'):
            content += '\n'
        
        file_path.write_text(content, encoding='utf-8')
        print(f"Updated {file_path}")
    
    def _get_file_header(self, file_path: Path, lang: str) -> Optional[str]:
        """Extract header comment from existing file or create default."""
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8')
            # Extract everything before first "key" = "value" line
            match = re.search(r'^"[^"]+"\s*=', content, re.MULTILINE)
            if match:
                header = content[:match.start()].strip()
                if header:
                    return header
        
        # Default header
        lang_names = {
            'en': 'English',
            'ru': 'Russian',
            'de': 'German',
            'es': 'Spanish',
            'fr': 'French',
            'it': 'Italian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'pt-BR': 'Portuguese (Brazil)',
            'tr': 'Turkish',
            'uk': 'Ukrainian',
            'zh-Hans': 'Chinese Simplified'
        }
        
        lang_name = lang_names.get(lang, lang)
        return f"""/* 
  Localizable.strings
  
  {lang_name}
*/
"""
    
    def _save_yaml(self) -> None:
        """Save translations to YAML file."""
        # Convert to OrderedDict for prettier output
        ordered = OrderedDict()
        
        for key in sorted(self.translations.keys()):
            ordered[key] = OrderedDict()
            # Put 'en' first if it exists
            if 'en' in self.translations[key]:
                ordered[key]['en'] = self.translations[key]['en']
            
            # Then other languages alphabetically
            for lang in sorted(self.translations[key].keys()):
                if lang != 'en':
                    ordered[key][lang] = self.translations[key][lang]
        
        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(ordered, f, 
                     default_flow_style=False, 
                     allow_unicode=True,
                     sort_keys=False,
                     width=120)
        
        print(f"Saved translations to {self.yaml_path}")
    
    def _load_yaml(self) -> None:
        """Load translations from YAML file."""
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.translations = data or {}
        self.languages = set()
        
        # Collect all languages
        for key, langs in self.translations.items():
            if isinstance(langs, dict):
                self.languages.update(langs.keys())
    
    def _report_missing_keys(self) -> None:
        """Report which keys are missing in which languages."""
        missing_found = False
        
        for key in self.translations:
            missing_langs = self.languages - set(self.translations[key].keys())
            if missing_langs:
                if not missing_found:
                    print("\nMissing translations:")
                    missing_found = True
                print(f"  {key}: missing in {', '.join(sorted(missing_langs))}")
        
        if not missing_found:
            print("All keys present in all languages ✓")