"""Dataset commands."""

from __future__ import annotations

from pathlib import Path

import click

from agentest.cli._main import console, main


@main.group()
def dataset() -> None:
    """Manage test datasets."""
    pass


main.add_command(dataset)


@dataset.command("create")
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output path.")
@click.option("--description", "-d", type=str, default="", help="Dataset description.")
def dataset_create(name: str, output: str | None, description: str) -> None:
    """Create a new empty dataset."""
    from agentest.datasets import Dataset

    ds = Dataset(name=name, description=description)
    path = output or f"datasets/{name}.yaml"
    ds.save(path)
    console.print(f"Created dataset: [cyan]{path}[/cyan]")


@dataset.command("list")
@click.argument("path", type=click.Path(exists=True))
def dataset_list(path: str) -> None:
    """List test cases in a dataset."""
    from agentest.datasets import Dataset

    ds = Dataset.load(path)
    console.print(f"[bold]{ds.name}[/bold] v{ds.version} ({ds.size} test cases)")

    if ds.description:
        console.print(f"  {ds.description}")

    for tc in ds.test_cases:
        tags = f" [{', '.join(tc.tags)}]" if tc.tags else ""
        console.print(f"  - {tc.name}: {tc.task}{tags}")


@dataset.command("split")
@click.argument("path", type=click.Path(exists=True))
@click.option("--ratio", type=float, default=0.5, help="Split ratio for group A.")
@click.option("--seed", type=int, default=42, help="Random seed.")
@click.option("--output-dir", "-o", type=click.Path(), default=None, help="Output directory.")
def dataset_split(path: str, ratio: float, seed: int, output_dir: str | None) -> None:
    """Split a dataset into two groups for A/B testing."""
    from agentest.datasets import Dataset

    ds = Dataset.load(path)
    a, b = ds.split(ratio=ratio, seed=seed)

    out_dir = Path(output_dir) if output_dir else Path(path).parent
    path_a = a.save(out_dir / f"{ds.name}_A.yaml")
    path_b = b.save(out_dir / f"{ds.name}_B.yaml")

    console.print(f"Split {ds.name} ({ds.size} cases) into:")
    console.print(f"  Group A: {a.size} cases -> [cyan]{path_a}[/cyan]")
    console.print(f"  Group B: {b.size} cases -> [cyan]{path_b}[/cyan]")
