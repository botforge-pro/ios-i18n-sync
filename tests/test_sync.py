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
        # Already positional - keep as is
        ("%1$d of %2$d", "%1$d of %2$d"),
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