"""Command-line interface for i18n-sync."""

import sys
from collections.abc import Callable

import click
import yaml

from .sync import I18nSync


@click.group()
def cli():
    """iOS i18n sync tool for managing .strings files through YAML."""


@cli.command()
@click.option(
    "--resources",
    "-r",
    default="Resources",
    help="Path to Resources directory (default: Resources)",
)
@click.option(
    "--output",
    "-o",
    default="translations.yaml",
    help="Output YAML file (default: translations.yaml)",
)
@click.option(
    "--source-lang",
    "-s",
    default="en",
    help="Source language that defines the canonical key list (default: en)",
)
def extract(resources, output, source_lang):
    """Extract all .strings files to translations.yaml."""
    try:
        sync = I18nSync(
            resources_path=resources, yaml_path=output, source_lang=source_lang
        )
        sync.extract()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, yaml.YAMLError) as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--input",
    "-i",
    default="translations.yaml",
    help="Input YAML file (default: translations.yaml)",
)
@click.option(
    "--resources",
    "-r",
    default="Resources",
    help="Path to Resources directory (default: Resources)",
)
def apply(input, resources):
    """Apply translations.yaml back to .strings files."""
    try:
        sync = I18nSync(resources_path=resources, yaml_path=input)
        sync.apply()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, yaml.YAMLError) as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command("convert-to-catalog")
@click.option(
    "--resources",
    "-r",
    default="Resources",
    help="Path to Resources directory (default: Resources)",
)
@click.option(
    "--source-lang",
    "-s",
    default="en",
    help="Source language of the catalog (default: en)",
)
def convert_to_catalog(resources, source_lang):
    """Move Localizable .strings and .stringsdict into Localizable.xcstrings."""
    try:
        I18nSync(resources_path=resources, source_lang=source_lang).convert_to_catalog()
    except (FileNotFoundError, FileExistsError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError) as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command("apply-android")
@click.option(
    "--input",
    "-i",
    default="translations.yaml",
    help="Input YAML file (default: translations.yaml)",
)
@click.option(
    "--res",
    "-r",
    default="app/src/main/res",
    help="Path to Android res directory (default: app/src/main/res)",
)
@click.option(
    "--default-lang",
    "-d",
    default="en",
    help="Default language for values/ folder (default: en)",
)
def apply_android(input, res, default_lang):
    """Apply translations.yaml to Android strings.xml files."""
    try:
        sync = I18nSync(yaml_path=input)
        sync.apply_android(res_path=res, default_lang=default_lang)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, yaml.YAMLError) as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


YAML_OPTION = click.option(
    "--input",
    "-i",
    "yaml_path",
    default="translations.yaml",
    help="YAML file to edit (default: translations.yaml)",
)
SOURCE_OPTION = click.option(
    "--source-lang",
    "-s",
    default="en",
    help="Source language, which cannot be removed or renamed (default: en)",
)


def edit_yaml(change: Callable[[], None]) -> None:
    try:
        change()
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (OSError, yaml.YAMLError) as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command("remove-language")
@YAML_OPTION
@SOURCE_OPTION
@click.argument("languages", nargs=-1, required=True)
def remove_language(
    yaml_path: str, source_lang: str, languages: tuple[str, ...]
) -> None:
    """Drop languages from every key of the YAML; apply then removes their files."""
    sync = I18nSync(yaml_path=yaml_path, source_lang=source_lang)
    edit_yaml(lambda: sync.remove_languages(list(languages)))


@cli.command("rename-language")
@YAML_OPTION
@SOURCE_OPTION
@click.argument("old")
@click.argument("new")
def rename_language(yaml_path: str, source_lang: str, old: str, new: str) -> None:
    """Move every translation from one language code to another, such as es-MX to es."""
    sync = I18nSync(yaml_path=yaml_path, source_lang=source_lang)
    edit_yaml(lambda: sync.rename_language(old, new))


@cli.command("remove-key")
@YAML_OPTION
@click.argument("keys", nargs=-1, required=True)
def remove_key(yaml_path: str, keys: tuple[str, ...]) -> None:
    """Drop keys from every section and from the plurals of the YAML."""
    edit_yaml(lambda: I18nSync(yaml_path=yaml_path).remove_keys(list(keys)))


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
