"""Classes and methods associated with packaging up inputs for nodes. Specifically, a Docker Compose Pydantic model class using the Nebula Docker image to mount the node config.

```python
# node: NebulaNode
d = get_docker_compose(node)
write_compose(d, "docker-compose.yaml")
```

"""

import glob
import os
import zipfile
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Union

import yaml
from pydantic import (BaseModel, Field, computed_field, field_serializer,
                      model_serializer)

from . import base as _base
from . import io as _io


class DockerService(BaseModel):
    image: str = _io.nebula_image
    container_name: str = "nebula"
    volumes: List[str]
    ports: List[str] = ["4242:4242"]


class DockerCompose(BaseModel):
    services: Mapping[str, DockerService]


def get_docker_compose(node) -> DockerCompose:
    """[TODO:description]

    Args:
        node: [TODO:description]

    Returns:
        [TODO:return]
    """
    config_path = _io.NODE_CONFIG_TEMPLATE.format(name=node.name)
    ds = DockerService(
        container_name=f"nebula_node_{node.name}",
        volumes=[f"{config_path}:/etc/nebula/{config_path}"],
        ports=[f"{node.port}:{node.port}"],
    )
    return DockerCompose(services={"nebula_node": ds})


def write_compose(model, output=None) -> None | str:
    yamlstr = yaml.dump(model.model_dump())
    if output is None:
        return yamlstr
    with open(output, "wt") as f:
        f.write(yamlstr)


def save_compose(network, node):
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
        compose_path = network.temp.node_compose(node)
        yield write_compose(
            get_docker_compose(node),
            output=compose_path.format(
                node_name=node.name,
            ),
        )


def save_composes(network, node):
    """[TODO:description]

    Args:
        network ([TODO:parameter]): [TODO:description]
        node ([TODO:parameter]): [TODO:description]

    Yields:
        [TODO:description]
    """
    yield save_compose(network, node)


def export(archivepath, outputs=[], out_glob=None):
    """[TODO:description]

    Args:
        archivepath ([TODO:parameter]): [TODO:description]
        outputs ([TODO:parameter]): [TODO:description]
        out_glob ([TODO:parameter]): [TODO:description]
    """
    if out_glob is not None:
        outputs += glob.glob(out_glob)
    with zipfile.ZipFile(archivepath, "w") as f:
        for path in outputs:
            f.write(path, arcname=os.path.split(path)[-1])
