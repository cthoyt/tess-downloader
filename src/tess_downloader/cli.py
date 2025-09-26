"""Command line interface for :mod:`tess_downloader`."""

import click

__all__ = [
    "main",
]


@click.command()
def main() -> None:
    """Download TeSS resources."""
    from tqdm import tqdm

    from .api import INSTANCES, TeSSClient

    for key in tqdm(INSTANCES):
        try:
            TeSSClient(key=key).cache()
        except Exception as e:
            click.secho(f"[{key}] failed: {e}")


if __name__ == "__main__":
    main()
