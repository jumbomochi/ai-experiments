"""CLI entrypoint for gold-set curation pipeline.

Usage:
    uv run python -m shared.goldsets.cli validate-seed gold_sets/general/seed.jsonl
    uv run python -m shared.goldsets.cli push --lane general --argilla-url http://<ip>:6900
    uv run python -m shared.goldsets.cli export --lane general --out gold_sets/general/annotated.jsonl
    uv run python -m shared.goldsets.cli load --file gold_sets/general/annotated.jsonl --version v0.1 --sha <sha>
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from shared.goldsets.validate_seed import validate_seed
from shared.goldsets.argilla_push import push_lane
from shared.goldsets.argilla_export import export_lane
from shared.goldsets.loader import load_jsonl_to_postgres

_DEFAULT_API_KEY = "owner.apikey"


@click.group()
def cli() -> None:
    """Gold-set curation pipeline commands."""


@cli.command("validate-seed")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def cmd_validate_seed(file: Path) -> None:
    """Validate a seed JSONL against the SeedExample schema."""
    errors = validate_seed(file)
    if errors:
        for err in errors:
            click.echo(f"ERROR: {err}", err=True)
        sys.exit(1)
    click.echo(f"OK: {file} is valid")


@cli.command("push")
@click.option("--lane", required=True, type=str)
@click.option("--argilla-url", required=True, type=str)
@click.option("--api-key", default=_DEFAULT_API_KEY, type=str, show_default=True)
@click.option("--seed-file", default=None, type=click.Path(path_type=Path),
              help="Path to seed JSONL (default: gold_sets/<lane>/seed.jsonl)")
def cmd_push(lane: str, argilla_url: str, api_key: str, seed_file: Path | None) -> None:
    """Push seed records to argilla (idempotent on example_id)."""
    if seed_file is None:
        seed_file = Path(f"gold_sets/{lane}/seed.jsonl")
    if not seed_file.exists():
        click.echo(f"ERROR: seed file not found: {seed_file}", err=True)
        sys.exit(1)
    n = push_lane(seed_file, lane=lane, argilla_url=argilla_url, api_key=api_key)
    click.echo(f"Pushed {n} new records to lane-{lane}")


@cli.command("export")
@click.option("--lane", required=True, type=str)
@click.option("--out", required=True, type=click.Path(path_type=Path))
@click.option("--argilla-url", required=True, type=str)
@click.option("--api-key", default=_DEFAULT_API_KEY, type=str, show_default=True)
@click.option("--seed-file", default=None, type=click.Path(path_type=Path),
              help="Seed JSONL to merge inputs from (default: gold_sets/<lane>/seed.jsonl if it exists)")
def cmd_export(lane: str, out: Path, argilla_url: str, api_key: str, seed_file: Path | None) -> None:
    """Export submitted argilla records to annotated JSONL."""
    if seed_file is None:
        default_seed = Path(f"gold_sets/{lane}/seed.jsonl")
        if default_seed.exists():
            seed_file = default_seed
    n = export_lane(lane=lane, out_path=out, argilla_url=argilla_url, api_key=api_key, seed_path=seed_file)
    click.echo(f"Exported {n} records to {out}")


@cli.command("load")
@click.option("--file", "jsonl_file", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--version", required=True, type=str)
@click.option("--sha", required=True, type=str, help="Git commit SHA of the annotated.jsonl")
@click.option("--test", is_flag=True, default=False, help="Use test DB")
def cmd_load(jsonl_file: Path, version: str, sha: str, test: bool) -> None:
    """Load annotated JSONL into Postgres."""
    n = load_jsonl_to_postgres(jsonl_file, version=version, git_commit_sha=sha, test=test)
    if n == 0:
        click.echo(f"No-op: version={version} sha={sha} already loaded")
    else:
        click.echo(f"Loaded {n} examples as version={version}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
