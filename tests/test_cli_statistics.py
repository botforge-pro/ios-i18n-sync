"""CLI statistics describe missing translations in each resource format."""

import json

import pytest
from click.testing import CliRunner

from i18n_sync.cli import cli


def unit(value):
    return {"stringUnit": {"state": "translated", "value": value}}


def plural(value):
    return {"variations": {"plural": {"other": unit(value)}}}


def write_catalog(resources, only_plurals=False):
    resources.mkdir()
    strings = {
        "days": {
            "extractionState": "manual",
            "localizations": {"en": plural("%lld days")},
        },
        "complete": {
            "extractionState": "manual",
            "localizations": {
                "en": plural("%lld files") if only_plurals else unit("OK"),
                "fr": plural("%lld fichiers") if only_plurals else unit("OK"),
            },
        },
    }
    path = resources / "Localizable.xcstrings"
    path.write_text(
        json.dumps({"sourceLanguage": "en", "strings": strings, "version": "1.0"}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("only_plurals", [False, True])
def test_extract_cli_reports_missing_plural_locale(tmp_path, only_plurals):
    resources = tmp_path / "Resources"
    write_catalog(resources, only_plurals)

    result = CliRunner().invoke(
        cli,
        [
            "extract",
            "--resources",
            str(resources),
            "--output",
            str(tmp_path / "t.yaml"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Plurals.days: missing in fr" in result.output
    assert "All keys present in all languages" not in result.output
    assert "keys from 2 languages" in result.output


@pytest.mark.parametrize("backend", ["catalog", "legacy", "mixed"])
def test_apply_cli_round_trip_summary_matches_written_resources(tmp_path, backend):
    resources = tmp_path / "Resources"
    if backend != "legacy":
        catalog = write_catalog(resources)
        before = json.loads(catalog.read_text(encoding="utf-8"))
    if backend != "catalog":
        section = "Localizable" if backend == "legacy" else "InfoPlist"
        for lang, content in [
            ("en", '"complete" = "OK";\n"missing" = "Missing";\n'),
            ("fr", '"complete" = "OK";\n'),
        ]:
            lproj = resources / f"{lang}.lproj"
            lproj.mkdir(parents=True, exist_ok=True)
            (lproj / f"{section}.strings").write_text(content, encoding="utf-8")
    yaml_path = tmp_path / "t.yaml"
    runner = CliRunner()
    extracted = runner.invoke(
        cli, ["extract", "--resources", str(resources), "--output", str(yaml_path)]
    )
    assert extracted.exit_code == 0, extracted.output

    applied = runner.invoke(
        cli, ["apply", "--resources", str(resources), "--input", str(yaml_path)]
    )

    assert applied.exit_code == 0, applied.output
    if backend != "legacy":
        assert json.loads(catalog.read_text(encoding="utf-8")) == before
        assert (
            "1 missing catalog translation(s) omitted; falling back to the source language"
            in applied.output
        )
    else:
        assert "omitted" not in applied.output
    if backend != "catalog":
        assert '"missing" = "";' in (
            resources / "fr.lproj" / f"{section}.strings"
        ).read_text(encoding="utf-8")
        assert "1 missing translation(s) written as empty strings" in applied.output
    else:
        assert "written as empty strings" not in applied.output
