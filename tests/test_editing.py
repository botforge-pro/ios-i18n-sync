"""Tests for the commands that edit translations.yaml and for removing a language."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from i18n_sync import I18nSync
from i18n_sync.cli import cli


@pytest.fixture
def temp_dir():
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def yaml_path(temp_dir):
    path = temp_dir / "translations.yaml"
    path.write_text(
        yaml.dump(
            {
                "Localizable": {
                    "save": {
                        "en": "Save",
                        "es-MX": "Guardar",
                        "ru": "Сохранить",
                        "tr": "Kaydet",
                    },
                    "old": {"en": "Old", "ru": "Старое"},
                },
                "Plurals": {
                    "points": {
                        "en": {"one": "%lld point", "other": "%lld points"},
                        "es-MX": {"one": "%lld punto", "other": "%lld puntos"},
                        "tr": {"other": "%lld puan"},
                    },
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_a_removed_language_leaves_every_key_and_plural(yaml_path):
    I18nSync(yaml_path=yaml_path).remove_languages(["tr", "es-MX"])

    data = read(yaml_path)
    assert data["Localizable"]["save"] == {"en": "Save", "ru": "Сохранить"}
    assert data["Plurals"]["points"] == {
        "en": {"one": "%lld point", "other": "%lld points"}
    }


@pytest.mark.parametrize(
    "languages, error",
    [
        (["en"], "en is the source language"),
        (["de"], "No translations in de"),
    ],
)
def test_removing_the_source_or_an_absent_language_is_refused(
    yaml_path, languages, error
):
    before = yaml_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        I18nSync(yaml_path=yaml_path).remove_languages(languages)

    assert yaml_path.read_text(encoding="utf-8") == before


def test_a_renamed_language_keeps_its_strings_and_plurals(yaml_path):
    I18nSync(yaml_path=yaml_path).rename_language("es-MX", "es")

    data = read(yaml_path)
    assert data["Localizable"]["save"]["es"] == "Guardar"
    assert "es-MX" not in data["Localizable"]["save"]
    assert data["Plurals"]["points"]["es"] == {
        "one": "%lld punto",
        "other": "%lld puntos",
    }


def test_renaming_onto_a_language_already_there_is_refused(yaml_path):
    with pytest.raises(ValueError, match="ru already has translations"):
        I18nSync(yaml_path=yaml_path).rename_language("tr", "ru")


def test_a_removed_key_leaves_the_strings_and_the_plurals(yaml_path):
    I18nSync(yaml_path=yaml_path).remove_keys(["old", "points"])

    data = read(yaml_path)
    assert list(data["Localizable"]) == ["save"]
    assert "Plurals" not in data


def test_a_misspelt_key_is_named_and_nothing_is_removed(yaml_path):
    with pytest.raises(ValueError, match="No such key: olf"):
        I18nSync(yaml_path=yaml_path).remove_keys(["old", "olf"])

    assert "old" in read(yaml_path)["Localizable"]


def test_apply_removes_the_files_of_a_language_the_yaml_no_longer_has(temp_dir):
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump({"Localizable": {"save": {"en": "Save"}}}), encoding="utf-8"
    )
    resources = temp_dir / "Resources"
    gone = resources / "tr.lproj"
    gone.mkdir(parents=True)
    (gone / "Localizable.strings").write_text('"save" = "Kaydet";\n', encoding="utf-8")
    (gone / "InfoPlist.strings").write_text('"CFBundleName" = "X";\n', encoding="utf-8")
    keeps = resources / "ar.lproj"
    keeps.mkdir()
    (keeps / "Localizable.strings").write_text('"save" = "حفظ";\n', encoding="utf-8")
    (keeps / "Main.storyboard").write_text("<document/>", encoding="utf-8")

    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    assert not gone.exists()
    assert sorted(path.name for path in keeps.iterdir()) == ["Main.storyboard"]
    assert (resources / "en.lproj" / "Localizable.strings").exists()


def test_apply_android_removes_strings_of_a_language_the_yaml_no_longer_has(temp_dir):
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump(
            {"Localizable": {"save": {"en": "Save", "ru": "Сохранить"}}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    res = temp_dir / "res"
    for folder in (
        "values-tr",
        "values-pt-rBR",
        "values-b+zh+Hant+TW",
        "values-night",
        "values-car",
        "values-v21",
    ):
        (res / folder).mkdir(parents=True)
        (res / folder / "strings.xml").write_text("<resources/>", encoding="utf-8")
    (res / "values-tr" / "themes.xml").write_text("<resources/>", encoding="utf-8")

    I18nSync(yaml_path=yaml_path).apply_android(res_path=res)

    assert sorted(path.name for path in res.iterdir()) == [
        "values",
        "values-car",
        "values-night",
        "values-ru",
        "values-tr",
        "values-v21",
        "xml",
    ]
    assert [path.name for path in (res / "values-tr").iterdir()] == ["themes.xml"]
    assert (res / "values-night" / "strings.xml").exists()


def test_apply_leaves_a_lproj_without_files_of_its_own_and_says_nothing(
    temp_dir, capsys
):
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump({"Localizable": {"save": {"en": "Save"}}}), encoding="utf-8"
    )
    base = temp_dir / "Resources" / "Base.lproj"
    base.mkdir(parents=True)
    (base / "Main.storyboard").write_text("<document/>", encoding="utf-8")

    I18nSync(resources_path=temp_dir / "Resources", yaml_path=yaml_path).apply()

    assert (base / "Main.storyboard").exists()
    assert "Xcode project" not in capsys.readouterr().out


def unit(value):
    return {"stringUnit": {"state": "translated", "value": value}}


def by_device(mac, other):
    return {"variations": {"device": {"mac": unit(mac), "other": unit(other)}}}


def test_a_removed_language_leaves_the_catalog_whole(temp_dir, capsys):
    resources = temp_dir / "Resources"
    resources.mkdir()
    catalog = resources / "Localizable.xcstrings"
    catalog.write_text(
        json.dumps(
            {
                "sourceLanguage": "en",
                "version": "1.0",
                "strings": {
                    "ok": {"localizations": {"en": unit("OK"), "tr": unit("Tamam")}},
                    "tap": {
                        "localizations": {
                            "en": by_device("Click", "Tap"),
                            "tr": by_device("Tıkla", "Dokun"),
                            "ja": by_device("クリック", "タップ"),
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump({"Localizable": {"ok": {"en": "OK"}}}), encoding="utf-8"
    )

    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    strings = json.loads(catalog.read_text(encoding="utf-8"))["strings"]
    assert list(strings["ok"]["localizations"]) == ["en"]
    assert sorted(strings["tap"]["localizations"]) == ["en", "ja"]
    out = capsys.readouterr().out
    assert "Remove tr from the localizations of the Xcode project too" in out
    assert "Remove ja" not in out


def test_a_yaml_without_catalog_strings_leaves_the_catalog_and_its_languages(
    temp_dir, capsys
):
    resources = temp_dir / "Resources"
    resources.mkdir()
    catalog = resources / "Localizable.xcstrings"
    strings = {"hello": {"localizations": {"en": unit("Hello"), "fr": unit("Bonjour")}}}
    catalog.write_text(
        json.dumps({"sourceLanguage": "en", "version": "1.0", "strings": strings}),
        encoding="utf-8",
    )
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump({"InfoPlist": {"CFBundleName": {"en": "App", "fr": "Appli"}}}),
        encoding="utf-8",
    )

    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    assert json.loads(catalog.read_text(encoding="utf-8"))["strings"] == strings
    out = capsys.readouterr().out
    assert "is left as it is" in out
    assert "Xcode project" not in out


def test_apply_android_without_a_language_removes_nothing(temp_dir):
    yaml_path = temp_dir / "translations.yaml"
    yaml_path.write_text(
        yaml.dump({"AppShortcuts": {"Open": {"en": "Open", "fr": "Ouvrir"}}}),
        encoding="utf-8",
    )
    res = temp_dir / "res"
    (res / "values-fr").mkdir(parents=True)
    (res / "values-fr" / "strings.xml").write_text("<resources/>", encoding="utf-8")

    I18nSync(yaml_path=yaml_path).apply_android(res_path=res)

    assert (res / "values-fr" / "strings.xml").exists()


def test_the_command_names_what_it_refused(yaml_path):
    result = CliRunner().invoke(
        cli, ["remove-language", "--input", str(yaml_path), "de"]
    )

    assert result.exit_code == 1
    assert "No translations in de" in result.output


def test_the_commands_edit_the_yaml_from_the_command_line(yaml_path):
    runner = CliRunner()

    assert (
        runner.invoke(cli, ["remove-language", "-i", str(yaml_path), "tr"]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            cli, ["rename-language", "-i", str(yaml_path), "es-MX", "es"]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(cli, ["remove-key", "-i", str(yaml_path), "old"]).exit_code == 0
    )

    data = read(yaml_path)
    assert data["Localizable"] == {
        "save": {"en": "Save", "es": "Guardar", "ru": "Сохранить"}
    }
