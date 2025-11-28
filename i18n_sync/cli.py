"""Command-line interface for i18n-sync."""

import click
import sys
from pathlib import Path
from .sync import I18nSync


@click.group()
def cli():
    """iOS i18n sync tool for managing .strings files through YAML."""
    pass


@cli.command()
@click.option('--resources', '-r', default='Resources',
              help='Path to Resources directory (default: Resources)')
@click.option('--output', '-o', default='translations.yaml',
              help='Output YAML file (default: translations.yaml)')
def extract(resources, output):
    """Extract all .strings files to translations.yaml."""
    try:
        sync = I18nSync(resources_path=resources, yaml_path=output)
        sync.extract()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', default='translations.yaml',
              help='Input YAML file (default: translations.yaml)')
@click.option('--resources', '-r', default='Resources',
              help='Path to Resources directory (default: Resources)')
def apply(input, resources):
    """Apply translations.yaml back to .strings files."""
    try:
        sync = I18nSync(resources_path=resources, yaml_path=input)
        sync.apply()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command('apply-android')
@click.option('--input', '-i', default='translations.yaml',
              help='Input YAML file (default: translations.yaml)')
@click.option('--res', '-r', default='app/src/main/res',
              help='Path to Android res directory (default: app/src/main/res)')
@click.option('--default-lang', '-d', default='en',
              help='Default language for values/ folder (default: en)')
def apply_android(input, res, default_lang):
    """Apply translations.yaml to Android strings.xml files."""
    try:
        sync = I18nSync(yaml_path=input)
        sync.apply_android(res_path=res, default_lang=default_lang)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()