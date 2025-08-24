![Tests](https://github.com/botforge-pro/ios-i18n-sync/workflows/Tests/badge.svg)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org)

# iOS i18n Sync

Manage iOS localization files (`.strings`) through a single YAML file. No more editing dozens of separate files for each language.

## Why?

- 📝 **Single source of truth** - All translations in one YAML file
- 🔍 **Easy to review** - See all languages for each key side by side
- ✅ **Find missing translations** - Instantly see which keys are missing in which languages
- 🚀 **Simple workflow** - Extract, edit, apply

## Installation

```bash
pip install git+https://github.com/botforge-pro/ios-i18n-sync.git
```

## Usage

From your iOS project root:

```bash
# Extract all .strings files to translations.yaml
i18n-sync extract --resources Resources

# Edit translations.yaml with your favorite editor
# Then apply changes back:
i18n-sync apply --resources Resources
```

Default paths:
- Resources: `Resources/` directory
- YAML file: `translations.yaml`

## YAML Format

```yaml
cancel:
  en: "Cancel"
  ru: "Отмена"
  de: "Abbrechen"
  es: "Cancelar"
  
save:
  en: "Save"
  ru: "Сохранить"
  de: "Speichern"
  es: "Guardar"
```

## Features

- Preserves file headers (comments at the top of .strings files)
- Sorts keys alphabetically in YAML
- Reports missing translations during extract
- Handles Unicode correctly

## Why no `check` command?

The `extract` command already serves as a check - it reports the status of all translations when extracting to YAML. You'll see output like:
- `All keys present in all languages ✓` - Everything is consistent
- Missing keys are reported per language if found

There's no need for a separate `check` command since `extract` is non-destructive to your .strings files and provides all the validation information you need.