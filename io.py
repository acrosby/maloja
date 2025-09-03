"""Methods for wrangling Network and Node files on disk between the local filesystem and Nebula Docker container."""

import os
import tarfile
from io import BytesIO
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Union

import docker
import yaml

NODE_CONFIG_TEMPLATE = "{name}.yaml"
NODE_COMPOSE_TEMPLATE = "{name}_docker-compose.yml"
NEBULA_IMAGE_VERSION = "latest"
"""Nebula Docker image tag label"""
NEBULA_IMAGE = "nebulaoss/nebula"
"""Nebula Docker image base"""
nebula_image = f"{NEBULA_IMAGE}:{NEBULA_IMAGE_VERSION}"
"""Full Nebula Docker image string"""


dclient = docker.DockerClient()


def make_temp_dir(network=None, dir=None):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        dir ([TODO:parameter]): [TODO:description]

    Returns:
        [TODO:return]
    """
    if network is not None:
        dir = network.temp.dir
    assert dir is not None

    if not os.path.exists(dir):
        os.mkdir(dir)
    return dir


def node_outputs(
    network,
    node,
    exist: bool | Literal["any", "all"] = False,
    assert_exist=False,
    rm_exist=False,
):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        node ([TODO:parameter]): [TODO:description]
        assert_exist ([TODO:parameter]): [TODO:description]
        rm_exist ([TODO:parameter]): [TODO:description]
        exist: [TODO:description]

    Returns:
        [TODO:return]
    """
    fs = []
    for ext in ("crt", "key", "png"):
        fs.append(f"{network.temp.node_cert_prefix(node)}.{ext}")
        if assert_exist:
            assert os.path.exists(fs[-1])
        if rm_exist:
            if os.path.exists(fs[-1]):
                os.unlink(fs[-1])
    if not exist:
        return fs
    else:
        if exist == "all":
            return all([os.path.exists(f) for f in fs])
        elif exist == "any":
            return any([os.path.exists(f) for f in fs])


def ca_outputs(
    network,
    exist: bool | Literal["any", "all"] = False,
    assert_exist=False,
    rm_exist=False,
):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        assert_exist ([TODO:parameter]): [TODO:description]
        rm_exist ([TODO:parameter]): [TODO:description]
        exist: [TODO:description]

    Returns:
        [TODO:return]
    """
    fs = []
    for ext in ("crt", "key", "png"):
        fs.append(f"{network.temp.ca_cert_prefix}.{ext}")
        if assert_exist:
            assert os.path.exists(fs[-1])
        if rm_exist:
            if os.path.exists(fs[-1]):
                os.unlink(fs[-1])
    if not exist:
        return fs
    else:
        if exist == "all":
            return all([os.path.exists(f) for f in fs])
        elif exist == "any":
            return any([os.path.exists(f) for f in fs])


def sign_nodes(
    network,
    overwrite=False,
):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        overwrite ([TODO:parameter]): [TODO:description]

    Yields:
        [TODO:description]
    """
    nodes = network.get_nodes()
    for node in nodes:
        yield sign_node(
            network,
            node,
            overwrite=overwrite,
        )


def get_working_dir(network):
    return f"{os.path.abspath(os.curdir)}"


def sign_node(
    network,
    node,
    overwrite=False,
):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        node ([TODO:parameter]): [TODO:description]
        overwrite ([TODO:parameter]): [TODO:description]

    Raises:
        ValueError: [TODO:throw]
    """
    make_temp_dir(network)
    network_cert(network=network)
    if overwrite:
        node_outputs(network, node, rm_exist=True)
    # else:
    # assert not node_outputs(network, node, exist="any")
    ca_files_prefix = network.temp.ca_cert_prefix
    node_cert, node_key, node_qr = node_outputs(network, node)
    cmd = f"sign -name {node.name} -ip {str(node.ip)}/{network.cidr} -ca-crt {ca_files_prefix}.crt -ca-key {ca_files_prefix}.key -out-crt {node_cert} -out-key {node_key} -out-qr {node_qr}"
    cname = f"{node.name}_sign_cert_docker"
    workingdir = get_working_dir(network)
    if not node_outputs(network, node, exist="all"):
        if node_outputs(network, node, exist="any"):
            raise ValueError(
                f"Missing some of the following files: {node_cert}, {node_key}, and {node_qr}"
            )
        try:
            cert_container = dclient.containers.run(
                name=cname,
                image=nebula_image,
                command=cmd,
                entrypoint="/nebula-cert",
                # auto_remove=True,
                remove=True,
                detach=False,
                working_dir=workingdir,
                volumes=[f"{workingdir}:{workingdir}"],
            )
        except Exception as me:
            raise me


def network_cert(network, overwrite=False):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        overwrite ([TODO:parameter]): [TODO:description]

    Raises:
        ValueError: [TODO:throw]
    """
    make_temp_dir(network)
    ca_out = network.temp.ca_cert_prefix
    if overwrite:
        ca_outputs(network, rm_exist=True)
    # else:
    #     if ca_outputs(
    #         network,
    #         exist="any",
    #     )
    cmd = f"ca -name {network.cert_authority} -ips {network.network} -out-key {ca_out}.key -out-crt {ca_out}.crt -out-qr {ca_out}.png"
    cname = f"network_CA_certificate_{network.cert_authority}_docker"
    workingdir = get_working_dir(network)
    if not ca_outputs(network, exist="all"):
        if ca_outputs(network, exist="any"):
            f = ca_outputs(network)
            raise ValueError(f"Missing some of the following files: {f}")
        try:
            cert_container = dclient.containers.run(
                name=cname,
                image=nebula_image,
                command=cmd,
                entrypoint="/nebula-cert",
                auto_remove=True,
                detach=False,
                working_dir=workingdir,
                volumes=[f"{workingdir}:{workingdir}"],
            )
        except Exception as me:
            raise me


def save_config(network, node):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        node ([TODO:parameter]): [TODO:description]

    Yields:
        [TODO:description]
    """
    if node is not None:
        if type(node) is not str:
            name = node.name
    else:
        name = node
    nodes = network.get_nodes(name)
    for node in nodes:
        name = node.name
        config_output_path = network.temp.node_config(name)
        yield node.dump_config(
            output=config_output_path.format(
                node_name=node.name, ca=network.cert_authority
            )
        )


def save_configs(network, node=None):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        node ([TODO:parameter]): [TODO:description]

    Yields:
        [TODO:description]
    """
    yield save_config(network, node)
