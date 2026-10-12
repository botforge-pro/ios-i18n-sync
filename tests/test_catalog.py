"""Tests for String Catalog (.xcstrings) support."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from i18n_sync import I18nSync
from i18n_sync.catalog import widen_integer_specifiers

STRINGSDICT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>words</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>{one}</string>
            <key>other</key>
            <string>{other}</string>
        </dict>
    </dict>
</dict>
</plist>
"""


@pytest.fixture
def resources():
    temp = Path(tempfile.mkdtemp())
    resources = temp / "Resources"
    for lang, strings, one, other in [
        (
            "en",
            '"cancel" = "Cancel";\n"length" = "Length %d";\n',
            "%d word",
            "%d words",
        ),
        ("ru", '"cancel" = "Отмена";\n', "%d слово", "%d слов"),
    ]:
        lproj = resources / f"{lang}.lproj"
        lproj.mkdir(parents=True)
        (lproj / "Localizable.strings").write_text(strings, encoding="utf-8")
        (lproj / "Localizable.stringsdict").write_text(
            STRINGSDICT.format(one=one, other=other), encoding="utf-8"
        )
    (resources / "en.lproj" / "InfoPlist.strings").write_text(
        '"CFBundleDisplayName" = "App";\n', encoding="utf-8"
    )
    yield resources
    shutil.rmtree(temp)


def catalog(resources: Path) -> dict:
    return json.loads((resources / "Localizable.xcstrings").read_text(encoding="utf-8"))


def test_convert_moves_localizable_strings_and_plurals_into_one_catalog(resources):
    I18nSync(resources_path=resources).convert_to_catalog()

    strings = catalog(resources)["strings"]
    assert strings["cancel"]["extractionState"] == "manual"
    assert strings["cancel"]["localizations"]["ru"]["stringUnit"]["value"] == "Отмена"
    assert (
        strings["length"]["localizations"]["en"]["stringUnit"]["value"] == "Length %lld"
    )
    plural = strings["words"]["localizations"]["ru"]["variations"]["plural"]
    assert plural["other"]["stringUnit"]["value"] == "%lld слов"
    assert not (resources / "en.lproj" / "Localizable.strings").exists()
    assert not (resources / "ru.lproj").exists()
    assert (resources / "en.lproj" / "InfoPlist.strings").exists()


def test_a_missing_translation_is_left_out_so_the_source_shows(resources):
    I18nSync(resources_path=resources).convert_to_catalog()

    localizations = catalog(resources)["strings"]["length"]["localizations"]
    assert set(localizations) == {"en"}


def test_extract_and_apply_go_through_the_catalog(resources):
    yaml_path = resources.parent / "translations.yaml"
    I18nSync(resources_path=resources).convert_to_catalog()
    data = json.loads((resources / "Localizable.xcstrings").read_text(encoding="utf-8"))
    data["strings"]["cancel"]["comment"] = "Dismisses a sheet"
    (resources / "Localizable.xcstrings").write_text(json.dumps(data), encoding="utf-8")

    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    extracted = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert extracted["Localizable"]["cancel"] == {"en": "Cancel", "ru": "Отмена"}
    assert extracted["Plurals"]["words"]["en"] == {
        "one": "%lld word",
        "other": "%lld words",
    }
    assert extracted["InfoPlist"]["CFBundleDisplayName"] == {"en": "App"}

    extracted["Localizable"]["length"]["ru"] = "Длина %lld"
    del extracted["Localizable"]["cancel"]
    extracted["Localizable"]["save"] = {"en": "Save", "ru": "Сохранить"}
    yaml_path.write_text(yaml.dump(extracted, allow_unicode=True), encoding="utf-8")
    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    strings = catalog(resources)["strings"]
    assert "cancel" not in strings
    assert strings["save"]["localizations"]["ru"]["stringUnit"]["value"] == "Сохранить"
    assert (
        strings["length"]["localizations"]["ru"]["stringUnit"]["value"] == "Длина %lld"
    )
    assert not (resources / "en.lproj" / "Localizable.strings").exists()
    assert not (resources / "en.lproj" / "Localizable.stringsdict").exists()


def test_apply_keeps_a_comment_written_in_the_catalog(resources):
    yaml_path = resources.parent / "translations.yaml"
    I18nSync(resources_path=resources).convert_to_catalog()
    data = catalog(resources)
    data["strings"]["cancel"]["comment"] = "Dismisses a sheet"
    (resources / "Localizable.xcstrings").write_text(json.dumps(data), encoding="utf-8")

    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    assert catalog(resources)["strings"]["cancel"]["comment"] == "Dismisses a sheet"


def test_a_plural_inside_a_sentence_becomes_a_substitution(resources):
    yaml_path = resources.parent / "translations.yaml"
    I18nSync(resources_path=resources).convert_to_catalog()
    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    extracted = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    extracted["Plurals"]["words"]["en"] = {
        "one": "%lld word",
        "other": "%lld words",
        "_format_key": "Only %#@count@ left",
    }
    yaml_path.write_text(yaml.dump(extracted, allow_unicode=True), encoding="utf-8")

    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    english = catalog(resources)["strings"]["words"]["localizations"]["en"]
    assert english["stringUnit"]["value"] == "Only %#@count@ left"
    substitution = english["substitutions"]["count"]
    assert substitution["formatSpecifier"] == "lld"
    assert (
        substitution["variations"]["plural"]["other"]["stringUnit"]["value"]
        == "%arg words"
    )

    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    again = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert again["Plurals"]["words"]["en"]["_format_key"] == "Only %#@count@ left"
    assert again["Plurals"]["words"]["en"]["other"] == "%lld words"


def test_a_plural_whose_forms_leave_out_the_number_becomes_a_substitution(resources):
    yaml_path = resources.parent / "translations.yaml"
    I18nSync(resources_path=resources).convert_to_catalog()
    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    extracted = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    extracted["Plurals"]["words"]["ru"] = {
        "one": "слово",
        "few": "слова",
        "other": "слов",
    }
    yaml_path.write_text(yaml.dump(extracted, allow_unicode=True), encoding="utf-8")

    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()

    russian = catalog(resources)["strings"]["words"]["localizations"]["ru"]
    assert russian["stringUnit"]["value"] == "%#@count@"
    plural = russian["substitutions"]["count"]["variations"]["plural"]
    assert plural["few"]["stringUnit"]["value"] == "слова"
    english = catalog(resources)["strings"]["words"]["localizations"]["en"]
    assert "variations" in english

    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    again = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert again["Plurals"]["words"]["ru"] == {
        "one": "слово",
        "few": "слова",
        "other": "слов",
    }


def write_catalog(resources: Path, strings: dict) -> None:
    (resources / "Localizable.xcstrings").write_text(
        json.dumps({"sourceLanguage": "en", "strings": strings, "version": "1.0"}),
        encoding="utf-8",
    )


def round_trip(resources: Path) -> dict:
    yaml_path = resources.parent / "translations.yaml"
    I18nSync(resources_path=resources, yaml_path=yaml_path).extract()
    I18nSync(resources_path=resources, yaml_path=yaml_path).apply()
    return catalog(resources)["strings"]


@pytest.fixture
def catalog_only(resources):
    for lproj in resources.glob("*.lproj"):
        for path in lproj.glob("Localizable.*"):
            path.unlink()
    return resources


def unit(value: str) -> dict:
    return {"stringUnit": {"state": "translated", "value": value}}


def test_a_variation_by_device_survives_extract_and_apply(catalog_only):
    device = {"variations": {"device": {"mac": unit("Click"), "other": unit("Tap")}}}
    write_catalog(
        catalog_only,
        {
            "tap": {"localizations": {"en": device}},
            "ok": {"localizations": {"en": unit("OK")}},
        },
    )

    strings = round_trip(catalog_only)

    assert strings["tap"]["localizations"]["en"] == device
    assert strings["ok"]["localizations"]["en"] == unit("OK")


def test_a_string_with_two_substitutions_survives_extract_and_apply(catalog_only):
    def plural(value):
        return {
            "argNum": 1,
            "formatSpecifier": "lld",
            "variations": {"plural": {"other": unit(value)}},
        }

    two = {
        **unit("%#@a@ in %#@b@"),
        "substitutions": {"a": plural("%arg files"), "b": plural("%arg folders")},
    }
    write_catalog(catalog_only, {"files": {"localizations": {"en": two}}})

    assert round_trip(catalog_only)["files"]["localizations"]["en"] == two


def test_a_plural_after_another_argument_takes_its_position(catalog_only):
    yaml_path = catalog_only.parent / "translations.yaml"
    write_catalog(catalog_only, {})
    yaml_path.write_text(
        yaml.dump(
            {
                "Plurals": {
                    "owns": {
                        "en": {
                            "_format_key": "%@ has %#@count@",
                            "one": "%lld file",
                            "other": "%lld of %lld files",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    I18nSync(resources_path=catalog_only, yaml_path=yaml_path).apply()

    substitution = catalog(catalog_only)["strings"]["owns"]["localizations"]["en"][
        "substitutions"
    ]["count"]
    assert substitution["argNum"] == 2
    other = substitution["variations"]["plural"]["other"]["stringUnit"]["value"]
    assert other == "%arg of %lld files"


def test_an_escaped_percent_is_neither_an_argument_nor_the_count(catalog_only):
    yaml_path = catalog_only.parent / "translations.yaml"
    write_catalog(catalog_only, {})
    yaml_path.write_text(
        yaml.dump(
            {
                "Plurals": {
                    "off": {
                        "en": {
                            "_format_key": "100%% done, %#@count@",
                            "one": "%% d %lld file",
                            "other": "%% d %lld files",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    I18nSync(resources_path=catalog_only, yaml_path=yaml_path).apply()

    substitution = catalog(catalog_only)["strings"]["off"]["localizations"]["en"][
        "substitutions"
    ]["count"]
    assert substitution["argNum"] == 1
    other = substitution["variations"]["plural"]["other"]["stringUnit"]["value"]
    assert other == "%% d %arg files"


def test_an_escaped_percent_survives_apply_and_extract(catalog_only):
    yaml_path = catalog_only.parent / "translations.yaml"
    write_catalog(catalog_only, {})
    forms = {
        "_format_key": "%%#@literal@ %#@count@",
        "one": "%%arg %lld file",
        "other": "%%arg %lld files",
    }
    yaml_path.write_text(
        yaml.dump({"Plurals": {"off": {"en": forms}}}), encoding="utf-8"
    )

    sync = I18nSync(resources_path=catalog_only, yaml_path=yaml_path)
    sync.apply()
    localization = catalog(catalog_only)["strings"]["off"]["localizations"]["en"]
    assert list(localization["substitutions"]) == ["count"]
    sync.extract()

    extracted = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert extracted["Plurals"]["off"]["en"] == forms


def test_old_strings_beside_the_catalog_are_refused(resources):
    I18nSync(resources_path=resources).convert_to_catalog()
    (resources / "en.lproj" / "Localizable.strings").write_text(
        '"a" = "A";\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Localizable.strings"):
        I18nSync(
            resources_path=resources, yaml_path=resources.parent / "t.yaml"
        ).extract()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("%d", "%lld"),
        ("%02d", "%02lld"),
        ("%i", "%lld"),
        ("%u", "%llu"),
        ("%1$d", "%1$lld"),
        ("%lld", "%lld"),
        ("%d%% de réduction", "%lld%% de réduction"),
        ("%% under", "%% under"),
        ("100%%d", "100%%d"),
        ("%%%d", "%%%lld"),
    ],
)
def test_integer_specifiers_widen_to_long_long(before, after):
    assert widen_integer_specifiers(before) == after


def test_convert_refuses_to_overwrite_a_catalog(resources):
    (resources / "Localizable.xcstrings").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        I18nSync(resources_path=resources).convert_to_catalog()
