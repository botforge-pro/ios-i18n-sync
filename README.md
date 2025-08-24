# iOS i18n Sync

Synchronize iOS `.strings` localization files through a single YAML file. Edit translations in one place instead of managing dozens of separate files.

## Installation

```bash
pip install -e git+https://github.com/botforge-pro/ios-i18n-sync.git#egg=ios-i18n-sync
```

## Usage

```bash
# Extract all .strings files to translations.yaml
i18n-sync extract

# Apply translations.yaml back to .strings files  
i18n-sync apply
```