![Tests](https://github.com/botforge-pro/ios-i18n-sync/workflows/Tests/badge.svg)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)

# iOS i18n Sync

Manage iOS localization files (`.strings`) through a single YAML file. No more editing dozens of separate files for each language. Automatically handles `Localizable.strings`, `InfoPlist.strings`, and `AppShortcuts.strings`.

## Why?

- 📝 **Single source of truth** - All translations in one YAML file
- 🔍 **Easy to review** - See all languages for each key side by side
- ✅ **Find missing translations** - Instantly see which keys are missing in which languages
- 🚀 **Simple workflow** - Extract, edit, apply
- 🎯 **Smart key routing** - Automatically puts `NS*` and `CF*` keys into InfoPlist.strings
- 🔢 **Plurals support** - Parses `.stringsdict` and generates Android `<plurals>`
- 🌐 **Per-app language** - Auto-generates `locales_config.xml` for Android

## Installation

```bash
pip install git+https://github.com/botforge-pro/ios-i18n-sync.git
```

## Usage

### iOS

From your iOS project root:

```bash
# Extract Localizable, InfoPlist, and AppShortcuts strings to translations.yaml
i18n-sync extract --resources Resources

# Edit translations.yaml with your favorite editor
# Then apply changes back:
i18n-sync apply --resources Resources
```

### Android

Generate Android `strings.xml` files from the same YAML:

```bash
# Generate strings.xml for all languages
i18n-sync apply-android --input translations.yaml --res app/src/main/res
```

This creates the proper Android resource structure:
```
res/
├── values/strings.xml           # Default (English)
├── values-ru/strings.xml        # Russian
├── values-zh-rCN/strings.xml    # Chinese Simplified
├── values-pt-rBR/strings.xml    # Portuguese Brazil
├── xml/locales_config.xml       # Per-app language support
└── ...
```

Language codes are automatically converted from iOS to Android format (e.g., `zh-Hans` → `zh-rCN`, `pt-BR` → `pt-rBR`).

### Plurals

iOS `.stringsdict` files are automatically parsed and converted to Android `<plurals>`:

```yaml
# In translations.yaml
Plurals:
  items_count:
    en:
      one: "%d item"
      other: "%d items"
    ru:
      one: "%d элемент"
      few: "%d элемента"
      many: "%d элементов"
      other: "%d элементов"
```

Generates Android:
```xml
<plurals name="items_count">
    <item quantity="one">%1$d item</item>
    <item quantity="other">%1$d items</item>
</plurals>
```

### Per-App Language Support

The tool automatically generates `locales_config.xml` for Android 13+ per-app language settings:

```xml
<?xml version="1.0" encoding="utf-8"?>
<locale-config xmlns:android="http://schemas.android.com/apk/res/android">
    <locale android:name="de" />
    <locale android:name="en" />
    <locale android:name="ru" />
    <locale android:name="zh-CN" />
</locale-config>
```

Reference it in your `AndroidManifest.xml`:
```xml
<application
    android:localeConfig="@xml/locales_config"
    ...>
```

The tool automatically:
- Extracts from `Localizable.strings`, `InfoPlist.strings`, and `AppShortcuts.strings`
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

- Handles multiple .strings files (`Localizable.strings`, `InfoPlist.strings`, `AppShortcuts.strings`)
- Parses `.stringsdict` for pluralization rules
- Generates Android `strings.xml` with proper `<plurals>` elements
- Auto-generates `locales_config.xml` for Android per-app language
- Converts iOS format specifiers to Android (`%@` → `%s`, positional args)
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
