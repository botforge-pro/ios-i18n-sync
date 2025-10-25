![Tests](https://github.com/botforge-pro/ios-i18n-sync/workflows/Tests/badge.svg)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)

# iOS i18n Sync

Manage iOS localization files (`.strings`) through a single YAML file. No more editing dozens of separate files for each language. Automatically handles both `Localizable.strings` and `InfoPlist.strings`.

## Why?

- 📝 **Single source of truth** - All translations in one YAML file
- 🔍 **Easy to review** - See all languages for each key side by side
- ✅ **Find missing translations** - Instantly see which keys are missing in which languages
- 🚀 **Simple workflow** - Extract, edit, apply
- 🎯 **Smart key routing** - Automatically puts `NS*` and `CF*` keys into InfoPlist.strings

## Installation

```bash
pip install git+https://github.com/botforge-pro/ios-i18n-sync.git
```

## Usage

From your iOS project root:

```bash
# Extract all .strings files (both Localizable and InfoPlist) to translations.yaml
i18n-sync extract --resources Resources

# Edit translations.yaml with your favorite editor
# Then apply changes back:
i18n-sync apply --resources Resources
```

The tool automatically:
- Extracts from both `Localizable.strings` and `InfoPlist.strings`
- Organizes translations into sections in YAML
- Preserves the structure when applying back

Default paths:
- Resources: `Resources/` directory
- YAML file: `translations.yaml`

## YAML Format

The YAML file is organized into sections corresponding to different .strings files:

```yaml
Localizable:
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

InfoPlist:
  CFBundleDisplayName:
    en: "My App"
    ru: "Мое приложение"
    de: "Meine App"
    es: "Mi aplicación"

  NSCameraUsageDescription:
    en: "This app needs camera access"
    ru: "Приложению нужен доступ к камере"
    de: "Diese App benötigt Kamerazugriff"
    es: "Esta aplicación necesita acceso a la cámara"
```

## Features

- Handles multiple .strings files (`Localizable.strings`, `InfoPlist.strings`)
- Organized YAML structure with sections
- Preserves file headers (comments at the top of .strings files)
- Sorts keys alphabetically within sections
- Reports missing translations during extract
- Handles Unicode correctly

## Why no `check` command?

The `extract` command already serves as a check - it reports the status of all translations when extracting to YAML. You'll see output like:
- `All keys present in all languages ✓` - Everything is consistent
- Missing keys are reported per language if found

There's no need for a separate `check` command since `extract` is non-destructive to your .strings files and provides all the validation information you need.