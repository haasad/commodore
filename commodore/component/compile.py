import os
from pathlib import Path as P
import shutil
import tempfile
from textwrap import dedent

import click
from kapitan.resources import inventory_reclass

from commodore.config import Config
from commodore.component import Component
from commodore.dependency_mgmt import fetch_jsonnet_libs, fetch_jsonnet_libraries
from commodore.helpers import kapitan_compile, relsymlink
from commodore.inventory import Inventory
from commodore.postprocess import postprocess_components


libs = [
    {
        "name": "kube-libsonnet",
        "repository": "https://github.com/bitnami-labs/kube-libsonnet",
        "files": [{"libfile": "kube.libsonnet", "targetfile": "kube.libjsonnet"}],
    }
]


def compile_component(
    config: Config, component_path, value_files, search_paths, output_path
):
    # Resolve all input to absolute paths to fix symlinks
    component_path = P(component_path).resolve()
    value_files = [P(f).resolve() for f in value_files]
    search_paths = [P(d).resolve() for d in search_paths]
    search_paths.append("./dependencies/")
    search_paths.append(component_path / "vendor")
    output_path = P(output_path).resolve()
    # Ignore 'component-' prefix in dir name
    component_name = component_path.stem.replace("component-", "")

    click.secho(f"Compile component {component_name}...", bold=True)

    temp_dir = P(tempfile.mkdtemp(prefix="component-")).resolve()
    original_working_dir = os.getcwd()
    os.chdir(temp_dir)
    try:
        if config.debug:
            click.echo(f"   > Created temp workspace: {temp_dir}")

        inv = Inventory(work_dir=temp_dir)
        component = Component(component_name, directory=component_path)
        config.register_component(component)
        _prepare_fake_inventory(inv, component, value_files)

        # Create class for fake parameters
        with open(inv.classes_dir / "fake.yml", "w") as file:
            file.write(
                dedent(
                    f"""
                parameters:
                  cloud:
                    provider: cloudscale
                    region: rma1
                  cluster:
                    catalog_url: ssh://git@git.example.com/org/repo.git
                    dist: test-distribution
                    name: c-green-test-1234
                  customer:
                    name: t-silent-test-1234
                  argocd:
                    namespace: test

                  kapitan:
                    vars:
                        target: {component_name}
                        namespace: test"""
                )
            )

        # Create test target
        with open(inv.target_file(component), "w") as file:
            value_classes = "\n".join([f"- {c.stem}" for c in value_files])
            file.write(
                dedent(
                    f"""
                classes:
                - fake
                - defaults.{component_name}
                - components.{component_name}
                {value_classes}"""
                )
            )

        # Fake Argo CD lib
        # We plug "fake" Argo CD library here because every component relies on it
        # and we don't want to provide it every time when compiling a single component.
        inv.lib_dir.mkdir(exist_ok=True)
        with open(inv.lib_dir / "argocd.libjsonnet", "w") as file:
            file.write(
                dedent(
                    """
                local ArgoApp(component, namespace, project='', secrets=true) = {};
                local ArgoProject(name) = {};

                {
                  App: ArgoApp,
                  Project: ArgoProject,
                }"""
                )
            )

        # Fetch Jsonnet libs
        fetch_jsonnet_libs(config, libs)
        if (component_path / "jsonnetfile.json").exists():
            fetch_jsonnet_libraries(component_path)

        # Compile component
        kapitan_compile(
            config,
            [component_name],
            output_dir=output_path,
            search_paths=search_paths,
            fake_refs=True,
            reveal=True,
        )
        click.echo(
            f" > Component compiled to {output_path / 'compiled' / component_name}"
        )

        # prepare inventory and fake component object for postprocess
        nodes = inventory_reclass(inv.inventory_dir)["nodes"]
        # We change the working directory to the output_path directory here,
        # as postprocess expects to find `compiled/<target>` in the working
        # directory.
        os.chdir(output_path)
        postprocess_components(config, nodes, config.get_components())
    finally:
        os.chdir(original_working_dir)
        if config.trace:
            click.echo(f" > Temp dir left in place {temp_dir}")
        else:
            if config.debug:
                click.echo(f" > Remove temp dir {temp_dir}")
            shutil.rmtree(temp_dir)


def _prepare_fake_inventory(inv: Inventory, component: Component, value_files):
    component_class_file = component.class_file
    component_defaults_file = component.defaults_file
    if not component_class_file.exists():
        raise click.ClickException(
            f"Could not find component class file: {component_class_file}"
        )
    if not component_defaults_file.exists():
        raise click.ClickException(
            f"Could not find component default file: {component_defaults_file}"
        )

    for d in [
        inv.components_dir,
        inv.defaults_dir,
        inv.targets_dir,
        inv.dependencies_dir,
    ]:
        os.makedirs(d, exist_ok=True)
    # Create class symlink
    relsymlink(component_class_file, inv.components_dir)
    # Create defaults symlink
    relsymlink(
        component_defaults_file,
        inv.defaults_dir,
        dest_name=f"{component.name}.yml",
    )
    # Create component symlink
    relsymlink(component.target_directory, inv.dependencies_dir, component.name)
    # Create value symlinks
    for file in value_files:
        relsymlink(file.parent / file.name, inv.classes_dir)
