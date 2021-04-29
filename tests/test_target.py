"""
Unit-tests for target generation
"""

import os
import click
import pytest

from pathlib import Path as P
from textwrap import dedent

from commodore import cluster
from commodore.inventory import Inventory
from commodore.config import Config


@pytest.fixture
def data():
    """
    Setup test data
    """

    tenant = {
        "id": "mytenant",
        "displayName": "My Test Tenant",
    }
    cluster = {
        "id": "mycluster",
        "displayName": "My Test Cluster",
        "tenant": tenant["id"],
        "facts": {
            "distribution": "rancher",
            "cloud": "cloudscale",
        },
        "gitRepo": {
            "url": "ssh://git@git.example.com/cluster-catalogs/mycluster",
        },
    }
    return {
        "cluster": cluster,
        "tenant": tenant,
    }


def cluster_from_data(data) -> cluster.Cluster:
    return cluster.Cluster(data["cluster"], data["tenant"])


def _setup_working_dir(inv: Inventory, components):
    for cls in components:
        defaults = inv.defaults_file(cls)
        os.makedirs(defaults.parent, exist_ok=True)
        defaults.touch()
        component = inv.component_file(cls)
        os.makedirs(component.parent, exist_ok=True)
        component.touch()


def test_render_bootstrap_target(tmp_path: P):
    components = ["foo", "bar"]
    inv = Inventory(work_dir=tmp_path)
    _setup_working_dir(inv, components)

    target = cluster.render_target(inv, "cluster", ["foo", "bar", "baz"])

    classes = [
        "params.cluster",
        "defaults.foo",
        "defaults.bar",
        "global.commodore",
    ]
    assert target != ""
    print(target)
    assert len(target["classes"]) == len(
        classes
    ), "rendered target includes different amount of classes"
    for i in range(len(classes)):
        assert target["classes"][i] == classes[i]
    assert target["parameters"]["_instance"] == "cluster"


def test_render_target(tmp_path: P):
    components = ["foo", "bar"]
    inv = Inventory(work_dir=tmp_path)
    _setup_working_dir(inv, components)

    target = cluster.render_target(inv, "foo", ["foo", "bar", "baz"])

    classes = [
        "params.cluster",
        "defaults.foo",
        "defaults.bar",
        "global.commodore",
        "components.foo",
    ]
    assert target != ""
    print(target)
    assert len(target["classes"]) == len(
        classes
    ), "rendered target includes different amount of classes"
    for i in range(len(classes)):
        assert target["classes"][i] == classes[i]
    assert target["parameters"]["kapitan"]["vars"]["target"] == "foo"
    assert target["parameters"]["_instance"] == "foo"


def test_render_aliased_target(tmp_path: P):
    components = ["foo", "bar"]
    inv = Inventory(work_dir=tmp_path)
    _setup_working_dir(inv, components)

    target = cluster.render_target(inv, "fooer", ["foo", "bar", "baz"], component="foo")

    classes = [
        "params.cluster",
        "defaults.foo",
        "defaults.bar",
        "global.commodore",
        "components.foo",
    ]
    assert target != ""
    print(target)
    assert len(target["classes"]) == len(
        classes
    ), "rendered target includes different amount of classes"
    for i in range(len(classes)):
        assert target["classes"][i] == classes[i]
    assert target["parameters"]["kapitan"]["vars"]["target"] == "fooer"
    assert target["parameters"]["foo"] == "${fooer}"
    assert target["parameters"]["_instance"] == "fooer"


def test_render_aliased_target_with_dash(tmp_path: P):
    components = ["foo-comp", "bar"]
    inv = Inventory(work_dir=tmp_path)
    _setup_working_dir(inv, components)

    target = cluster.render_target(
        inv, "foo-1", ["foo-comp", "bar", "baz"], component="foo-comp"
    )

    classes = [
        "params.cluster",
        "defaults.foo-comp",
        "defaults.bar",
        "global.commodore",
        "components.foo-comp",
    ]
    assert target != ""
    print(target)
    assert len(target["classes"]) == len(
        classes
    ), "rendered target includes different amount of classes"
    for i in range(len(classes)):
        assert target["classes"][i] == classes[i]
    assert target["parameters"]["kapitan"]["vars"]["target"] == "foo-1"
    assert target["parameters"]["foo_comp"] == "${foo_1}"
    assert target["parameters"]["_instance"] == "foo-1"


def test_render_params(data, tmp_path: P):
    cfg = Config(work_dir=tmp_path)
    target = cfg.inventory.bootstrap_target
    params = cluster.render_params(cfg.inventory, cluster_from_data(data))
    assert params["parameters"]["cluster"]["name"] == "mycluster"
    assert params["parameters"][target]["name"] == "mycluster"
    assert params["parameters"][target]["display_name"] == "My Test Cluster"
    assert (
        params["parameters"][target]["catalog_url"]
        == "ssh://git@git.example.com/cluster-catalogs/mycluster"
    )
    assert params["parameters"][target]["tenant"] == "mytenant"
    assert params["parameters"][target]["tenant_display_name"] == "My Test Tenant"
    assert params["parameters"][target]["dist"] == "rancher"
    assert params["parameters"]["facts"] == data["cluster"]["facts"]
    assert params["parameters"]["cloud"]["provider"] == "cloudscale"
    assert params["parameters"]["customer"]["name"] == "mytenant"


def test_missing_facts(data, tmp_path: P):
    data["cluster"]["facts"].pop("cloud")
    cfg = Config(work_dir=tmp_path)
    with pytest.raises(click.ClickException):
        cluster.render_params(cfg.inventory, cluster_from_data(data))


def test_empty_facts(data, tmp_path: P):
    data["cluster"]["facts"]["cloud"] = ""
    cfg = Config(work_dir=tmp_path)
    with pytest.raises(click.ClickException):
        cluster.render_params(cfg.inventory, cluster_from_data(data))


def test_read_cluster_and_tenant(tmp_path):
    cfg = Config(work_dir=tmp_path)
    file = cfg.inventory.params_file
    os.makedirs(file.parent, exist_ok=True)
    with open(file, "w") as f:
        f.write(
            dedent(
                """
            parameters:
              cluster:
                name: c-twilight-water-9032
                tenant: t-delicate-pine-3938"""
            )
        )

    cluster_id, tenant_id = cluster.read_cluster_and_tenant(cfg.inventory)
    assert cluster_id == "c-twilight-water-9032"
    assert tenant_id == "t-delicate-pine-3938"


def test_read_cluster_and_tenant_missing_fact(tmp_path):
    inv = Inventory(work_dir=tmp_path)
    file = inv.params_file
    os.makedirs(file.parent, exist_ok=True)
    with open(file, "w") as f:
        f.write(
            dedent(
                """
            classes: []
            parameters: {}"""
            )
        )

    with pytest.raises(KeyError):
        cluster.read_cluster_and_tenant(inv)
