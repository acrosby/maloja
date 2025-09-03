

.. note:: 
   This code in a very early stage and improvements are being made based on our use of it.


A Python package for creating, deploying and modifying Defined Networking's [Nebula](https://nebula.defined.net) mesh networking system using [Pydantic](https://pydantic.com.cn/en/) models.


> Nebula is an overlay networking tool designed to be fast, secure, and scalable. Connect any number of hosts with on-demand, encrypted tunnels that work across any IP networks and without opening firewall ports.

The name *Maloja* comes from the Maloja Snake, a long serpentine cloud formation produced by the foehn Maloja Wind in the Swiss Alps. `maloja` is an open source project not affiliated with Defined Networking.


```Python
import maloja

from maloja import NebulaNode, NebulaNetwork, RoutableIPPort
```


## Entities

Pydantic models/classes to represent nodes and network elements.
A `maloja.entities.NebulaNode` is a standalone entity separate from a `maloja.entities.NebulaNetwork`,
and all nodes including lighthouses and relays are constructed from the class.

```Python
nodes = [
    NebulaNode(
        name="lighthouse_node",
        am_lighthouse=True,
        public=RoutableIPPort(ip="10.50.60.134", port=4242),
    ),
    NebulaNode(name="other_node", groups=["rdp"]),
]

net = NebulaNetwork(
    cert_authority="My CA Inc",
    ip="10.100.200.0",
    cidr=24,
    nodes=nodes,
)

net.create_network_cert()
```

When a `NebulaNetwork` model is applied a node, it imposes additional configuration and functionality.
This includes automatically calculating Nebula IP addresses based on remaining addresses in the specified network.

```Python
net.create_node_cert()
```

## Config

`maloja.config` provides the classes reponsible for representing, validating and serializing the Nebula node yaml configuration file.

```Python
net.save_node_configs()
```

## I/O

The `maloja.io` submodule is contains methods for interacting with a containerized Nebula cli binary, and managing networking project outputs on disk.

## Deploy

Methods used standalone, with [Pyinfra](https://docs.pyinfra.com/en/3.x/index.html) or with [Docker](https://www.docker.com) to automate node and network management.

```Python
net.save_node_composes()
```



