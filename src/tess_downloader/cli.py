"""Command line interface for :mod:`tess_downloader`."""

import click

__all__ = [
    "main",
]


@click.command()
def main() -> None:
    """Download TeSS resources."""
    from .api import TeSSClient

    TeSSClient(key="tess", base_url="https://tess.elixir-europe.org/").cache()
    TeSSClient(key="taxila", base_url="https://taxila.nl/").cache()
    TeSSClient(key="scilifelab", base_url="https://training.scilifelab.se/").cache()


if __name__ == "__main__":
    main()
