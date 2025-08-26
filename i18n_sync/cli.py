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
@click.option('--strings-file', '-s', default='Localizable',
              help='Name of strings file without extension (default: Localizable)')
def extract(resources, output, strings_file):
    """Extract all .strings files to translations.yaml."""
    try:
        sync = I18nSync(resources_path=resources, yaml_path=output, strings_file=strings_file)
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
@click.option('--strings-file', '-s', default='Localizable',
              help='Name of strings file without extension (default: Localizable)')
def apply(input, resources, strings_file):
    """Apply translations.yaml back to .strings files."""
    try:
        sync = I18nSync(resources_path=resources, yaml_path=input, strings_file=strings_file)
        sync.apply()
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