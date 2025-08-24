"""Tests for I18nSync class."""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml
from i18n_sync import I18nSync


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
    
    def test_extract_basic(self, sample_resources, temp_dir):
        """Test basic extraction functionality."""
        yaml_path = temp_dir / "translations.yaml"
        sync = I18nSync(resources_path=sample_resources, yaml_path=yaml_path)
        
        sync.extract()
        
        assert yaml_path.exists()
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert "cancel" in data
        assert data["cancel"]["en"] == "Cancel"
        assert data["cancel"]["ru"] == "Отмена"
        assert data["cancel"]["de"] == "Abbrechen"
        
        assert "save" in data
        assert data["save"]["en"] == "Save"
        assert data["save"]["ru"] == "Сохранить"
        assert data["save"]["de"] == "Speichern"
        
        assert "delete" in data
        assert data["delete"]["en"] == "Delete"
        assert data["delete"]["de"] == "Löschen"
        # Russian is missing delete key
        assert "ru" not in data["delete"]
    
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
        
        assert data == {} or data is None


class TestApply:
    """Test applying YAML to .strings files."""
    
    def test_apply_basic(self, temp_dir):
        """Test basic apply functionality."""
        # Create YAML file
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "cancel": {
                "en": "Cancel",
                "ru": "Отмена",
                "de": "Abbrechen"
            },
            "save": {
                "en": "Save",
                "ru": "Сохранить",
                "de": "Speichern"
            }
        }
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)
        
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
        # Create YAML with missing translations
        yaml_path = temp_dir / "translations.yaml"
        yaml_data = {
            "cancel": {
                "en": "Cancel",
                "ru": "Отмена",
                "de": "Abbrechen"
            },
            "save": {
                "en": "Save",
                "ru": "Сохранить"
                # Missing German translation
            }
        }
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True)
        
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
        if "delete" in data:
            data["delete"]["ru"] = "Удалить"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True)
        
        # Apply back
        sync.apply()
        
        # Check Russian now has delete
        ru_file = sample_resources / "ru.lproj" / "Localizable.strings"
        content = ru_file.read_text(encoding='utf-8')
        assert '"delete" = "Удалить";' in content
        
        # Original keys still there
        assert '"cancel" = "Отмена";' in content
        assert '"save" = "Сохранить";' in content