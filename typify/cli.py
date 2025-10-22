import click
from typify import run_infer
from typify import run_build

@click.group()
def cli():
	"""Typify: Static Type Inference Tool"""
	pass

@cli.command()
@click.argument("project_dir", type=click.Path(exists=True))
@click.option("--output-dir", type=click.Path(), help="Output directory for inferred types.")
@click.option("--relative-to", type=click.Path(), help="Base directory for relative paths.")
@click.option("--log-level", default="off", type=click.Choice(["off","info","debug","trace","error","warning"]))
@click.option("--clear-cache", is_flag=True)
@click.option("--prune-cache", is_flag=True)
@click.option("--dont-cache", is_flag=True)
@click.option("--clear-output", is_flag=True)
@click.option("--heur", is_flag=True)
@click.option("--usage", is_flag=True)
def infer(**kwargs):
	"""Run usage-driven type inference on a Python project."""
	run_infer.run_inference(**kwargs)

@cli.command()
@click.option("--train-files", required=True, type=click.Path(exists=True))
@click.option("--output-json", default="type_index.json", show_default=True)
def build(train_files, output_json):
	"""Build a JSON type-context index from annotated Python files."""

	run_build.build_index(
		train_list_file=train_files,
		output_json=output_json
	)

def main():
	cli()

if __name__ == "__main__":
	main()
