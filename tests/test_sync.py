"""Tests for I18nSync class."""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml
from i18n_sync import I18nSync
from i18n_sync.models import TranslationsData


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def sample_resources(temp_dir):
    """Create sample .strings files for testing."""
    resources = temp_dir / "Resources"
    
    # English
    en_dir = resources / "en.lproj"
    en_dir.mkdir(parents=True)
    (en_dir / "Localizable.strings").write_text("""/* 
  Localizable.strings
  
  English
*/

"cancel" = "Cancel";
"save" = "Save";
"delete" = "Delete";
""", encoding='utf-8')
    
    # Russian
    ru_dir = resources / "ru.lproj"
    ru_dir.mkdir(parents=True)
    (ru_dir / "Localizable.strings").write_text("""/* 
  Localizable.strings
  
  Russian
*/

"cancel" = "Отмена";
"save" = "Сохранить";
// Missing "delete" key
""", encoding='utf-8')
    
    # German
    de_dir = resources / "de.lproj"
    de_dir.mkdir(parents=True)
    (de_dir / "Localizable.strings").write_text("""/* 
  Localizable.strings
  
  German
*/

"cancel" = "Abbrechen";
"save" = "Speichern";
"delete" = "Löschen";
""", encoding='utf-8')
    
    return resources


class TestExtract:
    """Test extraction from .strings to YAML."""

    def test_extract_escaped_quotes(self, temp_dir):
        """Test that escaped quotes inside strings are properly extracted."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        # String with escaped quotes inside
        (en_dir / "Localizable.strings").write_text("""/*
  Localizable.strings

  English
*/
"reportCurrent" = "Report \\"%@\\"";
"reportPrevious" = "Report previous \\"%@\\"";
""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert "Localizable" in data
        assert "reportCurrent" in data["Localizable"]
        assert data["Localizable"]["reportCurrent"]["en"] == 'Report "%@"'
        assert "reportPrevious" in data["Localizable"]
        assert data["Localizable"]["reportPrevious"]["en"] == 'Report previous "%@"'

    def test_extract_basic(self, sample_resources, temp_dir):
        """Test basic extraction functionality."""
        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=sample_resources, yaml_path=yaml_path)
        
        sync.extract()
        
        assert yaml_path.exists()
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert "Localizable" in data
        assert "cancel" in data["Localizable"]
        assert data["Localizable"]["cancel"]["en"] == "Cancel"
        assert data["Localizable"]["cancel"]["ru"] == "Отмена"
        assert data["Localizable"]["cancel"]["de"] == "Abbrechen"

        assert "save" in data["Localizable"]
        assert data["Localizable"]["save"]["en"] == "Save"
        assert data["Localizable"]["save"]["ru"] == "Сохранить"
        assert data["Localizable"]["save"]["de"] == "Speichern"

        assert "delete" in data["Localizable"]
        assert data["Localizable"]["delete"]["en"] == "Delete"
        assert data["Localizable"]["delete"]["de"] == "Löschen"
        # Russian is missing delete key
        assert "ru" not in data["Localizable"]["delete"]
    
    def test_extract_no_resources(self, temp_dir):
        """Test extraction fails gracefully when no resources found."""
        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=temp_dir / "nonexistent", yaml_path=yaml_path)
        
        with pytest.raises(FileNotFoundError):
            sync.extract()
    
    def test_extract_empty_strings_file(self, temp_dir):
        """Test extraction handles empty .strings files."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        (en_dir / "Localizable.strings").write_text("", encoding='utf-8')
        
        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        
        sync.extract()
        
        assert yaml_path.exists()
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert data == {"Localizable": {}} or data is None


class TestApply:
    """Test applying YAML to .strings files."""

    def test_apply_escapes_quotes(self, temp_dir):
        """Test that quotes inside strings are properly escaped."""
        yaml_path = temp_dir / "translations.yaml"

        trans_data = TranslationsData()
        section = trans_data.add_section("Localizable")
        section.add_key("reportCurrent", "en", 'Report "%@"')
        section.add_key("reportCurrent", "es", 'Informar "%@"')
        section.add_key("reportPrevious", "en", 'Report previous "%@"')
        section.add_key("reportPrevious", "es", 'Informar anterior "%@"')

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(trans_data.to_yaml_dict(), f, allow_unicode=True, sort_keys=False)

        # Apply
        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()

        # Check English file has properly escaped quotes
        en_file = resources / "en.lproj" / "Localizable.strings"
        assert en_file.exists()
        content = en_file.read_text(encoding='utf-8')
        assert '"reportCurrent" = "Report \\"%@\\"";' in content
        assert '"reportPrevious" = "Report previous \\"%@\\"";' in content

        # Check Spanish file
        es_file = resources / "es.lproj" / "Localizable.strings"
        assert es_file.exists()
        content = es_file.read_text(encoding='utf-8')
        assert '"reportCurrent" = "Informar \\"%@\\"";' in content
        assert '"reportPrevious" = "Informar anterior \\"%@\\"";' in content

    def test_apply_basic(self, temp_dir):
        """Test basic apply functionality."""
        yaml_path = temp_dir / "translations.yaml"

        trans_data = TranslationsData()
        section = trans_data.add_section("Localizable")
        section.add_key("cancel", "en", "Cancel")
        section.add_key("cancel", "ru", "Отмена")
        section.add_key("cancel", "de", "Abbrechen")
        section.add_key("save", "en", "Save")
        section.add_key("save", "ru", "Сохранить")
        section.add_key("save", "de", "Speichern")

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(trans_data.to_yaml_dict(), f, allow_unicode=True, sort_keys=False)
        
        # Apply
        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()
        
        # Check English file
        en_file = resources / "en.lproj" / "Localizable.strings"
        assert en_file.exists()
        content = en_file.read_text(encoding='utf-8')
        assert '"cancel" = "Cancel";' in content
        assert '"save" = "Save";' in content
        
        # Check Russian file
        ru_file = resources / "ru.lproj" / "Localizable.strings"
        assert ru_file.exists()
        content = ru_file.read_text(encoding='utf-8')
        assert '"cancel" = "Отмена";' in content
        assert '"save" = "Сохранить";' in content
        
        # Check German file
        de_file = resources / "de.lproj" / "Localizable.strings"
        assert de_file.exists()
        content = de_file.read_text(encoding='utf-8')
        assert '"cancel" = "Abbrechen";' in content
        assert '"save" = "Speichern";' in content
    
    def test_apply_missing_translation(self, temp_dir):
        """Test apply handles missing translations gracefully."""
        yaml_path = temp_dir / "translations.yaml"

        trans_data = TranslationsData()
        section = trans_data.add_section("Localizable")
        section.add_key("cancel", "en", "Cancel")
        section.add_key("cancel", "ru", "Отмена")
        section.add_key("cancel", "de", "Abbrechen")
        section.add_key("save", "en", "Save")
        section.add_key("save", "ru", "Сохранить")
        # Missing German translation for "save"

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(trans_data.to_yaml_dict(), f, allow_unicode=True, sort_keys=False)
        
        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()
        
        # German file should have empty value for missing key
        de_file = resources / "de.lproj" / "Localizable.strings"
        assert de_file.exists()
        content = de_file.read_text(encoding='utf-8')
        assert '"cancel" = "Abbrechen";' in content
        assert '"save" = "";' in content  # Missing translation gets empty value
    
    def test_apply_no_yaml(self, temp_dir):
        """Test apply fails gracefully when YAML doesn't exist."""
        resources = temp_dir / "Resources"
        yaml_path = temp_dir / "nonexistent.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        
        with pytest.raises(FileNotFoundError):
            sync.apply()


class TestDeadKeyRemoval:
    """Test that keys missing from en (source of truth) are dropped."""

    def test_extract_drops_keys_missing_from_en(self, temp_dir):
        """Keys that exist in other languages but NOT in en should be dropped during extract."""
        resources = temp_dir / "Resources"

        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        (en_dir / "Localizable.strings").write_text(
            '"cancel" = "Cancel";\n"save" = "Save";\n', encoding='utf-8'
        )

        ru_dir = resources / "ru.lproj"
        ru_dir.mkdir(parents=True)
        (ru_dir / "Localizable.strings").write_text(
            '"cancel" = "Отмена";\n"save" = "Сохранить";\n"deadKey" = "Мёртвый ключ";\n',
            encoding='utf-8',
        )

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert "cancel" in data["Localizable"]
        assert "save" in data["Localizable"]
        assert "deadKey" not in data["Localizable"]

    def test_round_trip_removes_deleted_keys(self, temp_dir):
        """Extract -> apply removes keys from other languages if deleted from en."""
        resources = temp_dir / "Resources"

        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        (en_dir / "Localizable.strings").write_text(
            '"cancel" = "Cancel";\n"save" = "Save";\n', encoding='utf-8'
        )

        ru_dir = resources / "ru.lproj"
        ru_dir.mkdir(parents=True)
        (ru_dir / "Localizable.strings").write_text(
            '"cancel" = "Отмена";\n"save" = "Сохранить";\n"deadKey" = "Мёртвый ключ";\n',
            encoding='utf-8',
        )

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()
        sync.apply()

        ru_content = (resources / "ru.lproj" / "Localizable.strings").read_text(encoding='utf-8')
        assert "deadKey" not in ru_content
        assert '"cancel" = "Отмена";' in ru_content
        assert '"save" = "Сохранить";' in ru_content

        en_content = (resources / "en.lproj" / "Localizable.strings").read_text(encoding='utf-8')
        assert "deadKey" not in en_content


class TestRoundTrip:
    """Test extract -> apply round trip."""

    def test_round_trip(self, sample_resources, temp_dir):
        """Test that extract -> apply preserves data."""
        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=sample_resources, yaml_path=yaml_path)
        
        # Extract
        sync.extract()
        
        # Modify to add missing translation
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Add missing Russian translation for "delete"
        if "Localizable" in data and "delete" in data["Localizable"]:
            data["Localizable"]["delete"]["ru"] = "Удалить"

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        
        # Apply back
        sync.apply()
        
        # Check Russian now has delete
        ru_file = sample_resources / "ru.lproj" / "Localizable.strings"
        content = ru_file.read_text(encoding='utf-8')
        assert '"delete" = "Удалить";' in content
        
        # Original keys still there
        assert '"cancel" = "Отмена";' in content
        assert '"save" = "Сохранить";' in content


class TestApplyAndroid:
    """Test applying YAML to Android strings.xml files."""

    def test_apply_android_basic(self, temp_dir):
        """Test basic Android strings.xml generation."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "cancel": {"en": "Cancel", "ru": "Отмена", "de": "Abbrechen"},
                "save": {"en": "Save", "ru": "Сохранить", "de": "Speichern"},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Check default (English) in values/
        default_file = res_path / "values" / "strings.xml"
        assert default_file.exists()
        content = default_file.read_text(encoding='utf-8')
        assert '<?xml version="1.0" encoding="utf-8"?>' in content
        assert '<string name="cancel">Cancel</string>' in content
        assert '<string name="save">Save</string>' in content

        # Check Russian in values-ru/
        ru_file = res_path / "values-ru" / "strings.xml"
        assert ru_file.exists()
        content = ru_file.read_text(encoding='utf-8')
        assert '<string name="cancel">Отмена</string>' in content
        assert '<string name="save">Сохранить</string>' in content

        # Check German in values-de/
        de_file = res_path / "values-de" / "strings.xml"
        assert de_file.exists()
        content = de_file.read_text(encoding='utf-8')
        assert '<string name="cancel">Abbrechen</string>' in content
        assert '<string name="save">Speichern</string>' in content

    def test_apply_android_language_mapping(self, temp_dir):
        """Test iOS to Android language code mapping."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "hello": {
                    "en": "Hello",
                    "zh-Hans": "你好",
                    "zh-Hant": "您好",
                    "zh-HK": "你好",
                    "pt-BR": "Olá",
                    "pt-PT": "Olá",
                    "es-419": "Hola",
                    "es-MX": "Hola",
                    "sr-Latn": "Zdravo",
                    "nb": "Hei",
                }
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Check language code mappings
        assert (res_path / "values" / "strings.xml").exists()  # en -> values/
        assert (res_path / "values-zh-rCN" / "strings.xml").exists()  # zh-Hans
        assert (res_path / "values-zh-rTW" / "strings.xml").exists()  # zh-Hant
        assert (res_path / "values-zh-rHK" / "strings.xml").exists()  # zh-HK
        assert (res_path / "values-pt-rBR" / "strings.xml").exists()  # pt-BR
        assert (res_path / "values-pt-rPT" / "strings.xml").exists()  # pt-PT
        assert (res_path / "values-b+es+419" / "strings.xml").exists()  # es-419
        assert (res_path / "values-es-rMX" / "strings.xml").exists()  # es-MX
        assert (res_path / "values-b+sr+Latn" / "strings.xml").exists()  # sr-Latn
        assert (res_path / "values-nb" / "strings.xml").exists()  # nb stays nb

    def test_apply_android_xml_escaping(self, temp_dir):
        """Test proper XML escaping in Android strings."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "apostrophe": {"en": "It's working"},
                "ampersand": {"en": "Tom & Jerry"},
                "quotes": {"en": 'Say "Hello"'},
                "less_than": {"en": "1 < 2"},
                "greater_than": {"en": "2 > 1"},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        assert "<string name=\"apostrophe\">It\\'s working</string>" in content
        assert "<string name=\"ampersand\">Tom &amp; Jerry</string>" in content
        assert '<string name="quotes">Say \\"Hello\\"</string>' in content
        assert "<string name=\"less_than\">1 &lt; 2</string>" in content
        assert "<string name=\"greater_than\">2 &gt; 1</string>" in content

    def test_apply_android_missing_translation(self, temp_dir):
        """Test that missing translations are skipped (not included in that language file)."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "cancel": {"en": "Cancel", "ru": "Отмена"},
                "save": {"en": "Save"},  # Missing Russian
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Russian file should only have cancel, not save
        ru_content = (res_path / "values-ru" / "strings.xml").read_text(encoding='utf-8')
        assert '<string name="cancel">Отмена</string>' in ru_content
        assert 'save' not in ru_content

    def test_apply_android_no_yaml(self, temp_dir):
        """Test apply_android fails gracefully when YAML doesn't exist."""
        res_path = temp_dir / "res"
        yaml_path = temp_dir / "nonexistent.yaml"
        sync = I18nSync(yaml_path=yaml_path)

        with pytest.raises(FileNotFoundError):
            sync.apply_android(res_path=res_path)

    def test_apply_android_sorted_keys(self, temp_dir):
        """Test that keys are sorted alphabetically in output."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "zebra": {"en": "Zebra"},
                "apple": {"en": "Apple"},
                "mango": {"en": "Mango"},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        apple_pos = content.find("apple")
        mango_pos = content.find("mango")
        zebra_pos = content.find("zebra")
        assert apple_pos < mango_pos < zebra_pos

    @pytest.mark.parametrize("ios_format,android_format", [
        # Single %@ -> %s
        ("%@ files", "%s files"),
        # Multiple format specifiers get positional args
        ("%d files of %d", "%1$d files of %2$d"),
        ("%d files of %d (%@)", "%1$d files of %2$d (%3$s)"),
        # Mixed types
        ("%@ has %d items", "%1$s has %2$d items"),
        # Already positional - keep as is (convert @ to s)
        ("%1$d of %2$d", "%1$d of %2$d"),
        ("%1$@ to %2$@", "%1$s to %2$s"),
        ("%1$@ has %2$d items (%3$@)", "%1$s has %2$d items (%3$s)"),
        # Single specifier - no positional needed
        ("%d items", "%d items"),
        ("%@ name", "%s name"),
        # Float
        ("%.2f MB", "%.2f MB"),
        ("%d of %d (%.1f%%)", "%1$d of %2$d (%3$.1f%%)"),
    ])
    def test_apply_android_format_specifiers(self, temp_dir, ios_format, android_format):
        """Test iOS format specifiers are converted to Android format."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "testKey": {"en": ios_format},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        assert f'<string name="testKey">{android_format}</string>' in content


class TestStringsdict:
    """Test parsing iOS .stringsdict files and generating Android plurals."""

    def test_extract_stringsdict(self, temp_dir):
        """Test extraction of plurals from .stringsdict files."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)

        # Create English stringsdict
        (en_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>flowTimeHours</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@hours@</string>
        <key>hours</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>%d hour</string>
            <key>other</key>
            <string>%d hours</string>
        </dict>
    </dict>
</dict>
</plist>""", encoding='utf-8')

        # Create Russian stringsdict with more plural forms
        ru_dir = resources / "ru.lproj"
        ru_dir.mkdir(parents=True)
        (ru_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>flowTimeHours</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@hours@</string>
        <key>hours</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>%d час</string>
            <key>few</key>
            <string>%d часа</string>
            <key>many</key>
            <string>%d часов</string>
            <key>other</key>
            <string>%d часов</string>
        </dict>
    </dict>
</dict>
</plist>""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Check plurals section exists
        assert "Plurals" in data
        assert "flowTimeHours" in data["Plurals"]

        # Check English plurals
        en_plurals = data["Plurals"]["flowTimeHours"]["en"]
        assert en_plurals["one"] == "%d hour"
        assert en_plurals["other"] == "%d hours"

        # Check Russian plurals (has more forms)
        ru_plurals = data["Plurals"]["flowTimeHours"]["ru"]
        assert ru_plurals["one"] == "%d час"
        assert ru_plurals["few"] == "%d часа"
        assert ru_plurals["many"] == "%d часов"
        assert ru_plurals["other"] == "%d часов"

    def test_apply_android_plurals(self, temp_dir):
        """Test generating Android plurals XML from YAML."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "cancel": {"en": "Cancel", "ru": "Отмена"},
            },
            "Plurals": {
                "flowTimeHours": {
                    "en": {"one": "%d hour", "other": "%d hours"},
                    "ru": {"one": "%d час", "few": "%d часа", "many": "%d часов", "other": "%d часов"},
                },
                "flowTimeMinutes": {
                    "en": {"one": "%d minute", "other": "%d minutes"},
                    "ru": {"one": "%d минуту", "few": "%d минуты", "many": "%d минут", "other": "%d минут"},
                },
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Check English plurals
        en_content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        assert '<plurals name="flowTimeHours">' in en_content
        assert '<item quantity="one">%d hour</item>' in en_content
        assert '<item quantity="other">%d hours</item>' in en_content
        assert '<plurals name="flowTimeMinutes">' in en_content

        # Check Russian plurals (has few/many)
        ru_content = (res_path / "values-ru" / "strings.xml").read_text(encoding='utf-8')
        assert '<plurals name="flowTimeHours">' in ru_content
        assert '<item quantity="one">%d час</item>' in ru_content
        assert '<item quantity="few">%d часа</item>' in ru_content
        assert '<item quantity="many">%d часов</item>' in ru_content
        assert '<item quantity="other">%d часов</item>' in ru_content

    def test_apply_android_plurals_escaping(self, temp_dir):
        """Test that plurals values are properly XML escaped."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Plurals": {
                "testPlural": {
                    "en": {"one": "%d file's size", "other": "%d files' sizes"},
                },
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        assert "<item quantity=\"one\">%d file\\'s size</item>" in content
        assert "<item quantity=\"other\">%d files\\' sizes</item>" in content


class TestLocalesConfig:
    """Test generating Android locales_config.xml for per-app language support."""

    def test_generates_locales_config(self, temp_dir):
        """Test that locales_config.xml is generated with all languages."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "hello": {"en": "Hello", "ru": "Привет", "de": "Hallo"},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Check locales_config.xml exists
        config_file = res_path / "xml" / "locales_config.xml"
        assert config_file.exists()

        content = config_file.read_text(encoding='utf-8')
        assert '<?xml version="1.0" encoding="utf-8"?>' in content
        assert '<locale-config xmlns:android="http://schemas.android.com/apk/res/android">' in content
        assert '<locale android:name="de" />' in content
        assert '<locale android:name="en" />' in content
        assert '<locale android:name="ru" />' in content
        assert '</locale-config>' in content

    def test_locales_config_sorted_alphabetically(self, temp_dir):
        """Test that locales are sorted alphabetically."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "hello": {"zh-Hans": "你好", "en": "Hello", "fr": "Bonjour", "ar": "مرحبا"},
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "xml" / "locales_config.xml").read_text(encoding='utf-8')
        ar_pos = content.find('android:name="ar"')
        en_pos = content.find('android:name="en"')
        fr_pos = content.find('android:name="fr"')
        zh_pos = content.find('android:name="zh-CN"')  # zh-Hans maps to zh-CN
        assert ar_pos < en_pos < fr_pos < zh_pos

    def test_locales_config_language_mapping(self, temp_dir):
        """Test that iOS language codes are mapped to Android format in locales_config."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "hello": {
                    "en": "Hello",
                    "zh-Hans": "你好",
                    "zh-Hant": "您好",
                    "pt-BR": "Olá",
                    "sr-Latn": "Zdravo",
                },
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        content = (res_path / "xml" / "locales_config.xml").read_text(encoding='utf-8')
        assert '<locale android:name="en" />' in content
        assert '<locale android:name="zh-CN" />' in content  # zh-Hans -> zh-CN
        assert '<locale android:name="zh-TW" />' in content  # zh-Hant -> zh-TW
        assert '<locale android:name="pt-BR" />' in content
        assert '<locale android:name="sr-Latn" />' in content


class TestApplyStringsdict:
    """Test applying YAML plurals to iOS .stringsdict files."""

    def test_apply_writes_stringsdict(self, temp_dir):
        """Test that apply() writes plurals from YAML to .stringsdict files."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "cancel": {"en": "Cancel", "ru": "Отмена"},
            },
            "Plurals": {
                "items.count": {
                    "en": {"one": "%d item", "other": "%d items"},
                    "ru": {"one": "%d элемент", "few": "%d элемента", "many": "%d элементов", "other": "%d элементов"},
                },
            },
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()

        # Check English stringsdict was created
        en_stringsdict = resources / "en.lproj" / "Localizable.stringsdict"
        assert en_stringsdict.exists(), "English .stringsdict not created"

        import plistlib
        with open(en_stringsdict, 'rb') as f:
            plist = plistlib.load(f)

        assert "items.count" in plist
        entry = plist["items.count"]
        assert entry["NSStringLocalizedFormatKey"] == "%#@count@"
        plural_dict = entry["count"]
        assert plural_dict["NSStringFormatSpecTypeKey"] == "NSStringPluralRuleType"
        assert plural_dict["NSStringFormatValueTypeKey"] == "d"
        assert plural_dict["one"] == "%d item"
        assert plural_dict["other"] == "%d items"

        # Check Russian stringsdict with more plural forms
        ru_stringsdict = resources / "ru.lproj" / "Localizable.stringsdict"
        assert ru_stringsdict.exists(), "Russian .stringsdict not created"

        with open(ru_stringsdict, 'rb') as f:
            plist = plistlib.load(f)

        ru_plural = plist["items.count"]["count"]
        assert ru_plural["one"] == "%d элемент"
        assert ru_plural["few"] == "%d элемента"
        assert ru_plural["many"] == "%d элементов"
        assert ru_plural["other"] == "%d элементов"

    def test_apply_stringsdict_preserves_existing_keys(self, temp_dir):
        """Test that apply() preserves existing stringsdict keys not in YAML."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)

        # Pre-existing stringsdict with a key
        (en_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>existing.plural</key>
\t<dict>
\t\t<key>NSStringLocalizedFormatKey</key>
\t\t<string>%#@count@</string>
\t\t<key>count</key>
\t\t<dict>
\t\t\t<key>NSStringFormatSpecTypeKey</key>
\t\t\t<string>NSStringPluralRuleType</string>
\t\t\t<key>NSStringFormatValueTypeKey</key>
\t\t\t<string>d</string>
\t\t\t<key>one</key>
\t\t\t<string>%d thing</string>
\t\t\t<key>other</key>
\t\t\t<string>%d things</string>
\t\t</dict>
\t</dict>
</dict>
</plist>""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Plurals": {
                "new.plural": {
                    "en": {"one": "%d file", "other": "%d files"},
                },
            },
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()

        import plistlib
        with open(en_dir / "Localizable.stringsdict", 'rb') as f:
            plist = plistlib.load(f)

        # Both keys should exist
        assert "existing.plural" in plist, "Pre-existing key was lost"
        assert "new.plural" in plist, "New key was not added"
        assert plist["existing.plural"]["count"]["one"] == "%d thing"
        assert plist["new.plural"]["count"]["one"] == "%d file"

    def test_apply_stringsdict_round_trip(self, temp_dir):
        """Test extract -> modify -> apply round trip for stringsdict."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)

        (en_dir / "Localizable.strings").write_text('"hello" = "Hello";\n', encoding='utf-8')
        (en_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>days.count</key>
\t<dict>
\t\t<key>NSStringLocalizedFormatKey</key>
\t\t<string>%#@count@</string>
\t\t<key>count</key>
\t\t<dict>
\t\t\t<key>NSStringFormatSpecTypeKey</key>
\t\t\t<string>NSStringPluralRuleType</string>
\t\t\t<key>NSStringFormatValueTypeKey</key>
\t\t\t<string>d</string>
\t\t\t<key>one</key>
\t\t\t<string>%d day</string>
\t\t\t<key>other</key>
\t\t\t<string>%d days</string>
\t\t</dict>
\t</dict>
</dict>
</plist>""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        # Add Russian plurals to YAML
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        data["Plurals"]["days.count"]["ru"] = {
            "one": "%d день",
            "few": "%d дня",
            "many": "%d дней",
            "other": "%d дней",
        }

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True)

        # Apply
        sync.apply()

        # Russian stringsdict should now exist
        import plistlib
        ru_stringsdict = resources / "ru.lproj" / "Localizable.stringsdict"
        assert ru_stringsdict.exists()

        with open(ru_stringsdict, 'rb') as f:
            plist = plistlib.load(f)

        assert "days.count" in plist
        assert plist["days.count"]["count"]["one"] == "%d день"
        assert plist["days.count"]["count"]["few"] == "%d дня"


class TestStringsdictWithFormatKey:
    """Test parsing iOS .stringsdict files with full format key (not just placeholder)."""

    def test_extract_stringsdict_with_per_language_format_key(self, temp_dir):
        """Test extraction of plurals where each language has its own NSStringLocalizedFormatKey."""
        resources = temp_dir / "Resources"

        # Create English stringsdict
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        (en_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>trialLimitTextsCount</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>Only %#@texts@ available for free. Unlimited access is only available with Premium.</string>
        <key>texts</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>%d text</string>
            <key>other</key>
            <string>%d texts</string>
        </dict>
    </dict>
</dict>
</plist>""", encoding='utf-8')

        # Create German stringsdict with different format_key
        de_dir = resources / "de.lproj"
        de_dir.mkdir(parents=True)
        (de_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>trialLimitTextsCount</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>Nur %#@texts@ kostenlos. Unbegrenzter Zugang nur mit Premium.</string>
        <key>texts</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>%d Text</string>
            <key>other</key>
            <string>%d Texte</string>
        </dict>
    </dict>
</dict>
</plist>""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Check plurals extracted
        assert "Plurals" in data
        assert "trialLimitTextsCount" in data["Plurals"]
        plural_data = data["Plurals"]["trialLimitTextsCount"]

        # Each language should have its own _format_key
        assert "en" in plural_data
        assert plural_data["en"]["_format_key"] == "Only %#@texts@ available for free. Unlimited access is only available with Premium."
        assert plural_data["en"]["one"] == "%d text"
        assert plural_data["en"]["other"] == "%d texts"

        assert "de" in plural_data
        assert plural_data["de"]["_format_key"] == "Nur %#@texts@ kostenlos. Unbegrenzter Zugang nur mit Premium."
        assert plural_data["de"]["one"] == "%d Text"
        assert plural_data["de"]["other"] == "%d Texte"

    def test_apply_android_plurals_with_per_language_format_key(self, temp_dir):
        """Test Android plurals use per-language format_key."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Plurals": {
                "trialLimitTextsCount": {
                    "en": {
                        "_format_key": "Only %#@texts@ available for free. Unlimited access is only available with Premium.",
                        "one": "%d text",
                        "other": "%d texts",
                    },
                    "de": {
                        "_format_key": "Nur %#@texts@ kostenlos. Unbegrenzter Zugang nur mit Premium.",
                        "one": "%d Text",
                        "other": "%d Texte",
                    },
                },
            }
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        res_path = temp_dir / "res"
        sync = I18nSync(yaml_path=yaml_path)
        sync.apply_android(res_path=res_path, default_lang="en")

        # Check English - should use English format_key
        en_content = (res_path / "values" / "strings.xml").read_text(encoding='utf-8')
        assert '<plurals name="trialLimitTextsCount">' in en_content
        assert '<item quantity="one">Only %d text available for free. Unlimited access is only available with Premium.</item>' in en_content
        assert '<item quantity="other">Only %d texts available for free. Unlimited access is only available with Premium.</item>' in en_content

        # Check German - should use German format_key
        de_content = (res_path / "values-de" / "strings.xml").read_text(encoding='utf-8')
        assert '<plurals name="trialLimitTextsCount">' in de_content
        assert '<item quantity="one">Nur %d Text kostenlos. Unbegrenzter Zugang nur mit Premium.</item>' in de_content
        assert '<item quantity="other">Nur %d Texte kostenlos. Unbegrenzter Zugang nur mit Premium.</item>' in de_content

    def test_extract_stringsdict_positional_plural(self, temp_dir):
        """Test extraction of stringsdict with positional plural variable like %2$#@var@."""
        resources = temp_dir / "Resources"
        en_dir = resources / "en.lproj"
        en_dir.mkdir(parents=True)
        (en_dir / "Localizable.strings").write_text('"x" = "x";\n', encoding='utf-8')
        (en_dir / "Localizable.stringsdict").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>settings.combinations</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%1$@ %2$#@combinations@</string>
        <key>combinations</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>possible combination</string>
            <key>other</key>
            <string>possible combinations</string>
        </dict>
    </dict>
</dict>
</plist>""", encoding='utf-8')

        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.extract()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert "Plurals" in data
        plural_data = data["Plurals"]["settings.combinations"]
        assert plural_data["en"]["one"] == "possible combination"
        assert plural_data["en"]["other"] == "possible combinations"
        assert plural_data["en"]["_format_key"] == "%1$@ %2$#@combinations@"

    def test_apply_stringsdict_positional_plural(self, temp_dir):
        """Test applying YAML with positional plural variable produces correct stringsdict."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "x": {"en": "x", "ru": "x"},
            },
            "Plurals": {
                "settings.combinations": {
                    "en": {
                        "_format_key": "%1$@ %2$#@combinations@",
                        "one": "possible combination",
                        "other": "possible combinations",
                    },
                    "ru": {
                        "_format_key": "%1$@ %2$#@combinations@",
                        "one": "возможная комбинация",
                        "few": "возможные комбинации",
                        "many": "возможных комбинаций",
                        "other": "возможных комбинаций",
                    },
                },
            },
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()

        import plistlib
        en_stringsdict = resources / "en.lproj" / "Localizable.stringsdict"
        assert en_stringsdict.exists()
        with open(en_stringsdict, 'rb') as f:
            plist = plistlib.load(f)

        entry = plist["settings.combinations"]
        assert entry["NSStringLocalizedFormatKey"] == "%1$@ %2$#@combinations@"
        assert "combinations" in entry
        plural_dict = entry["combinations"]
        assert plural_dict["NSStringFormatSpecTypeKey"] == "NSStringPluralRuleType"
        assert plural_dict["NSStringFormatValueTypeKey"] == "d"
        assert plural_dict["one"] == "possible combination"
        assert plural_dict["other"] == "possible combinations"

        ru_stringsdict = resources / "ru.lproj" / "Localizable.stringsdict"
        with open(ru_stringsdict, 'rb') as f:
            plist = plistlib.load(f)

        ru_plural = plist["settings.combinations"]["combinations"]
        assert ru_plural["one"] == "возможная комбинация"
        assert ru_plural["few"] == "возможные комбинации"
        assert ru_plural["many"] == "возможных комбинаций"

    def test_apply_stringsdict_key_level_format_key(self, temp_dir):
        """Test that _format_key at key level (not per-language) applies to all languages."""
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "Localizable": {
                "x": {"en": "x", "ru": "x"},
            },
            "Plurals": {
                "settings.combinations": {
                    "_format_key": "%1$@ %2$#@combinations@",
                    "en": {
                        "one": "possible combination",
                        "other": "possible combinations",
                    },
                    "ru": {
                        "one": "возможная комбинация",
                        "few": "возможные комбинации",
                        "many": "возможных комбинаций",
                        "other": "возможных комбинаций",
                    },
                },
            },
        }
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)

        resources = temp_dir / "Resources"
        sync = I18nSync(resources_path=resources, yaml_path=yaml_path)
        sync.apply()

        import plistlib
        for lang in ["en", "ru"]:
            stringsdict = resources / f"{lang}.lproj" / "Localizable.stringsdict"
            with open(stringsdict, 'rb') as f:
                plist = plistlib.load(f)
            assert plist["settings.combinations"]["NSStringLocalizedFormatKey"] == "%1$@ %2$#@combinations@"