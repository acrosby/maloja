""" """

from __future__ import annotations

import ipaddress
import os
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Union

import yaml
from pydantic import (BaseModel, Field, computed_field, field_serializer,
                      model_serializer)
from pydantic.networks import IPvAnyAddress, IPvAnyInterface, IPvAnyNetwork

from . import base as _base
from . import config as _config
from . import deploy as _deploy
from . import io as _io


class NebulaNode(BaseModel):
    """
    Pydantic model representing a node in a Nebula network.

    Node certificates and keys can be created along with the configuration yaml file when combined with a `NebulaNetwork`.

    ## Examples

    Basic node

    ```
    NebulaNode(name="mynode1")
    ```

    Lighthouse node

    ```
    NebulaNode(name="mylighthouse", am_lighthouse=True)
    ```

    Specify ip address rather than computing it automatically

    ```
    NebulaNode(name="myspecificnode", ip="10.10.100.5")
    ```

    """

    name: str
    """Name to use as a hostname for nebula node"""
    ip: IPvAnyAddress | None = None
    """IP address within Nebula network"""
    port: int = 4242
    """Nebula node port (default is 4242)."""
    am_lighthouse: bool = False
    """Boolean speciyfing if the node is a lighthouse (`am_lighthouse=True`) or not (defaut is False)."""
    public: _config.RoutableIPPort | None = None
    """Public routable IP (and optionally port) for lighthouse nodes."""
    config: _config.NebulaConfig | None = None
    """`config.NebulaConfig` Pydantic model class that stores the required node configuration for the Nebula binary."""
    groups: List[str | _config.InOutboundItem] = []
    """In and outbound firewall groups."""

    def dump_config(self, output=None):
        """Method for serializing `self.config` to YAML.

        Args:
            output (str | None): Path to output config YAML file if not None. If None (default), function returns YAML contents as string.

        Returns:
            str | None
        """
        assert self.config is not None
        yamlstr = yaml.dump(self.config.model_dump())
        if output is None:
            return yamlstr
        with open(output, "wt") as f:
            f.write(yamlstr)

    def get_firewall_items_from_groups(self):
        for i, group in enumerate(self.groups):
            if type(group) is str:
                self.groups[i] = _config.InOutboundItem(group=group)
        return _config.Firewall(outbound=self.groups, inbound=self.groups)


#     def to_zip(self):
#         pass
#
#     def to_tar(self):
#         if self._tar is None:
#             self._tar = tarfile.open(mode="w:", fileobj=BytesIO())
#
#     def to_container(self, tag, config_yaml=None):
#         assert os.path.exists(self.config.pki.ca)
#         # if not os.path.exists(self.config.pki.key):
#         # self.create_node_cert()
#         assert os.path.exists(self.config.pki.key)
#         assert os.path.exists(self.config.pki.cert)
#         if config_yaml is None:
#             config_yaml = f"{self.name}_config.yaml"
#             self.dump_config(output=config_yaml)
#         assert os.path.exists(config_yaml)
#         dockerfile = f"""FROM {nebula_image} AS base
# WORKDIR /etc/nebula
# COPY {self.config.pki.ca} .
# COPY {self.config.pki.key} .
# COPY {self.config.pki.cert} .
# COPY {config_yaml} config.yaml
# ENTRYPOINT /nebula
# CMD ['-c', 'config.yaml']"""
#         dpath = f"{self.name}.Dockerfile"
#         with open(dpath, "wt") as f:
#             f.write(dockerfile)
#         c.images.build(path="./", dockerfile=dpath, tag=tag, rm=True)


class _NebulaTempFiles(BaseModel):
    """[TODO:description]

    Attributes:
        network: [TODO:attribute]
    """

    network: NebulaNetwork

    @computed_field
    @property
    def dir(self) -> str:
        """Network outputs directory named after `self.network.cert_authority`"""
        return os.path.abspath(f"{self.network.cert_authority}")

    @computed_field
    @property
    def ca_cert_prefix(self) -> str:
        """Network CA output filename prefix (under `{self.dir}/`) based on CA name and network IP range"""
        return f"{self.dir}/{self.network.cert_authority}_{self.network.ip}_{self.network.cidr}"

    def node_cert_prefix(self, node):
        """[TODO:description]

        Args:
            node ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        if type(node) is not str:
            node = node.name
        return f"{self.dir}/{node}"

    def node_config(self, node):
        """[TODO:description]

        Args:
            node ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        if type(node) is not str:
            node = node.name
        config = _io.NODE_CONFIG_TEMPLATE.format(name=node)
        return f"{self.dir}/{config}"

    def node_compose(self, node):
        """[TODO:description]

        Args:
            node ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        if type(node) is not str:
            node = node.name
        compose = _io.NODE_COMPOSE_TEMPLATE.format(name=node)
        return f"{self.dir}/{compose}"


class NebulaNetwork(BaseModel):
    cert_authority: str
    ip: IPvAnyAddress
    nodes: List[NebulaNode] = []
    cidr: _base.CIDRLiteral = 24

    def model_post_init(self, context):
        # Strip/sanitize cert_authority str
        self.cert_authority = self.cert_authority.replace(" ", "")
        # Calculate any missing IP addresses
        h = set(ipaddress.ip_network(self.network).hosts())
        for node in self.nodes:
            _ip = node.ip
            if _ip is not None:
                h = h - set([_ip])
        hosts = sorted(list(h))
        for i, node in enumerate(filter(lambda x: x.ip is None, self.nodes)):
            node.ip = hosts[i]

    @computed_field
    @property
    def network(self) -> IPvAnyNetwork:
        """ """
        return IPvAnyNetwork(str(self.ip) + f"/{self.cidr}")

    @computed_field
    @property
    def lighthouses(self) -> List[NebulaNode]:
        """ """
        return list(filter(lambda n: n.am_lighthouse, self.nodes))

    @computed_field
    @property
    def temp(self) -> _NebulaTempFiles:
        """ """
        return _NebulaTempFiles(network=self)

    def create_network_cert(
        self,
    ):
        """[TODO:description]"""
        _io.network_cert(self)

    def create_node_cert(
        self,
    ):
        """[TODO:description]"""
        for node in self.nodes:
            _io.sign_node(
                self,
                node=node,
            )
            ca_cert, ca_key, ca_qr = _io.ca_outputs(self)
            node_cert, node_key, node_qr = _io.node_outputs(self, node)
            pki = _config.Pki(
                ca=ca_cert,
                cert=node_cert,
                key=node_key,
            )
            lh = _config.Lighthouse(am_lighthouse=node.am_lighthouse)
            fw = node.get_firewall_items_from_groups()
            if not node.am_lighthouse:
                shm = _config.StaticHostMap(
                    contents=dict([(n.ip, [n.public]) for n in self.lighthouses])
                )
            else:
                shm = _config.StaticHostMap()
            node.config = _config.NebulaConfig(
                pki=pki,
                static_host_map=shm,
                lighthouse=lh,
                firewall=fw,
            )

    def save_node_configs(self, node=None):
        """[TODO:description]

        Args:
            node ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        return [config for config in _io.save_config(self, node)]

    def save_node_composes(self, node=None):
        """[TODO:description]

        Args:
            node ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        return [compose for compose in _deploy.save_compose(self, node)]

    def get_nodes(self, filter=None):
        """[TODO:description]

        Args:
            filter ([TODO:parameter]): [TODO:description]

        Returns:
            [TODO:return]
        """
        if filter is None:
            return self.nodes
        else:
            return list(filter(lambda n: filter in n.name, self.nodes))
