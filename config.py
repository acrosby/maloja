"""
Encapsulation of the Nebula YAML config as Pydantic model classes.

`NebulaConfig` is the model holding the full configuration for a node, requiring `pki` and `static_host_map` to be specified at a minimum for a non-"lighthouse" (and non-relay) node.

## Node key certificates

```python
pki = Pki(
    ca="ca.key",
    cert="mynode.crt",
    key="mynode.key",
)
```

## Specify "lighthouse" node

```python
shm = StaticHostMap(
        contents=dict([(lighthouse.ip, [lighthouse.public])])
)
```

## Configure node

```python
config = NebulaConfig(
    pki=pki,
    static_host_map=shm,
)
```

Find the official and definitive Nebula documentation at [here](https://nebula.defined.net/docs/config/).
"""

from __future__ import annotations

import ipaddress
import os
import tarfile
from io import BytesIO
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Union

import docker
import yaml
from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_serializer,
    model_serializer,
)
from pydantic.networks import IPvAnyAddress, IPvAnyInterface, IPvAnyNetwork

from . import base as _base


class Pki(_base.SkipNoneField):
    """Nebula [PKI configuration](https://nebula.defined.net/docs/config/pki)"""

    ca: str
    """Path to certificate authority key or the key itself. """
    cert: str
    """Path to private node certificate or the cert itself. """
    key: str
    """Path to node public key or the key itself. """
    blocklist: List[str] | None = None
    """List of nodes to block in network"""
    disconnect_invalid: bool | None = Field(default=True)
    _skip = ["blocklist", "disconnect_invalid"]
    """Fields to skip during serialization if None"""


class RoutableIPPort(BaseModel):
    ip: IPvAnyAddress
    port: int

    @model_serializer
    def __str__(self) -> str:
        return f"{str(self.ip)}:{self.port}"


class NetworkIPRange(BaseModel):
    ip: IPvAnyAddress
    mask: _base.CIDRLiteral = Field(alias="cidr")
    allow: bool | None = Field(default=None)

    @model_serializer
    def __str__(self) -> str:
        return f"{str(self.ip)}/{self.cidr}"


class StaticMap(BaseModel):
    """Nebula [static_map configuration](https://nebula.defined.net/docs/config/static-map)

    Examples

        sm = StaticMap()
        NebulaConfig(static_map=sm)
    """

    cadence: int | str = "30s"  # int in s
    network: Literal["ip4", "ip6", "ip"] = "ip4"
    lookup_timeout: int | str = "250ms"  # int in ms


class LocalAllowList(BaseModel):
    interfaces: Dict[IPvAnyInterface, bool] | None


class MaskPort(BaseModel):
    mask: NetworkIPRange
    port: int


class LhDns(BaseModel):
    host: IPvAnyAddress
    port: int = Field(default=53)
    interval: int = Field(default=60)  # in s
    hosts: List[IPvAnyAddress] = Field(default=[])


class Lighthouse(_base.SkipNoneField):
    """Nebula [lighthouse config section](https://nebula.defined.net/docs/config/lighthouse)


    Normal node

        lh = Lighthouse()

    Lighthouse node

        lh = Lighthouse(am_lighthouse=True)

    """

    am_lighthouse: bool = Field(default=False)
    """Set to True if this node will serve as lighthouse (default is False)."""
    serve_dns: bool = Field(default=False)
    dns: LhDns | None = Field(default=None)
    remote_allow_list: Dict[NetworkIPRange, bool] | None = Field(default=None)
    remote_allow_ranges: Dict[NetworkIPRange, bool] | None = Field(default=None)
    local_allow_list: LocalAllowList | None = Field(default=None)
    advertise_addrs: List[RoutableIPPort] | None = None
    calculated_remotes: dict[NetworkIPRange, MaskPort] | None = None
    _skip = [
        "dns",
        "remote_allow_list",
        "remote_allow_ranges",
        "local_allow_list",
        "advertise_addrs",
        "calculated_remotes",
    ]


class Listen(BaseModel):
    """Nebula [listen config](https://nebula.defined.net/docs/config/listen)

    Examples

        listen = Listen()
        NebulaConfig(listen=listen, ...)
    """

    host: IPvAnyAddress = Field(
        default=IPvAnyAddress("::")
    )  # or IPvAnyA"ddress("0.0.0.0") to listen on any ipv4
    """Node network interface to listen on (default is '::' for all IPv4 and v6 interfaces)."""
    port: int = Field(default=4242)
    """Node port to use."""
    batch: int = Field(default=64)
    read_buffer: int = Field(default=10485760)
    write_buffer: int = Field(default=10485760)
    send_recv_error: Literal["always", "never", "private"] = Field(default="always")
    so_mark: int = Field(default=0)  # Only for linux

    @field_serializer("host")
    def stringify_host_address(self, host: IPvAnyAddress) -> str:
        return str(host)


class Punchy(BaseModel):
    """Nebula [listen config](https://nebula.defined.net/docs/config/listen)

    Examples

        punchy = Punchy()
        NebulaConfig(punchy=punchy, ...)
    """

    punch: bool = True
    "Default is True."
    respond: bool = False
    delay: str | int = Field(default="1s")  # int in s
    respond_delay: str | int = Field(default="5s")  # int in s


class AuthorizedUser(BaseModel):
    user: str
    keys: List[str]


class Sshd(_base.SkipNoneField):
    """Nebula [sshd config](https://nebula.defined.net/docs/config/sshd) to enable Nebula ssh"""

    enabled: bool = False
    """Default is False."""
    listen: RoutableIPPort | None = None
    host_key: str | None = None
    authorized_users: List[AuthorizedUser] | None = None
    trusted_cas: List[str] | None = None
    _skip = [
        "listen",
        "host_key",
        "authorized_users",
        "trusted_cas",
    ]


class Relay(_base.SkipNoneField):
    """Nebula [relay config](https://nebula.defined.net/docs/config/realy)

    Examples

    ```python
    relay = Relay(am_relay=True, use_relays=True)
    NebulaConfig(relay=relay, ...)
    ```
    """

    relays: List[IPvAnyAddress] | None = None
    """List of relays to use or None (default is None)."""
    am_relay: bool = False
    """Set this node to be a relay with `am_relay=True` (default is False)."""
    use_relays: bool = True
    """Enable or disable use of relay nodes (default is True)."""
    _skip = ["relays"]


class RouteMTU(BaseModel):
    mtu: int = 1300
    route: NetworkIPRange


class ViaItem(_base.SkipNoneField):
    gateway: str
    weight: Optional[int] = None
    _skip = ["weight"]


class UnsafeRoute(_base.SkipNoneField):
    route: str
    via: Union[str, List[ViaItem]]
    mtu: Optional[int] = None
    metric: Optional[int] = None
    install: Optional[bool] = None
    _skip = ["mtu", "metric", "install"]


class Tun(_base.SkipNoneField):
    """Nebula network device [interface](https://nebula.defined.net/docs/config/tun)

    Examples

    ```python
    tun= Tun(dev="mynebuladev")
    NebulaConfig(tun=tun, ...)
    ```
    """

    disabled: bool = False
    dev: str = Field(default="nebula01")
    """Network interface device name (default is 'nebula01')."""
    drop_local_broadcast: bool = False
    drop_multicast: bool = False
    tx_queue: int = 500  # length
    mtu: int = 1300  # 1300 default for internet based traffic
    routes: List[RouteMTU] | None = None
    unsafe_routes: List[UnsafeRoute] | None = None
    use_system_route_table: bool = False
    use_system_route_table_buffer_size: int = 0
    _skip = [
        "routes",
        "unsafe_routes",
    ]


class Logging(BaseModel):
    """Nebula [node logging](https://nebula.defined.net/docs/config/logging)

    Examples

    ```python
    logconfig = Logging()
    NebulaConfig(logging=logconfig, ...)
    ```
    """

    level: Literal["info", "error", "warn", "debug"] = "info"
    "Log level out of ['info', 'error', warn', 'debug']. Default is 'info'."
    format: Literal["json", "text"] = "text"
    """Set logging format to 'json' or 'text' (default is 'text')."""
    disable_timestamp: bool = True
    timestamp_format: str = "2006-01-02T15:04:05.000Z07:00"  # go date time formatting


class Stats(BaseModel):
    """Set statistics observability for Graphite or Prometheus."""

    type: Literal["graphite", "prometheus"] = "graphite"
    protocol: Literal["tcp", "udp"] | None = "tcp"
    host: RoutableIPPort = Field(alias="listen")
    interval: str | int = "10s"  # int in s
    # Prometheus
    path: str | None = None
    namespace: str | None = "prometheus"
    # Graphite
    prefix: str | None = Field(alias="subsystem")


class Handshakes(BaseModel):
    """Handshakes config!!!"""

    try_interval: str | int = "100ms"  # int in ms
    retries: int = 20


class Tunnels(BaseModel):
    """Tunnels config!!!!!"""

    drop_inactive: bool = False
    inactivity_timeout: str | int = "10m"  # int in m


class Conntrack(BaseModel):
    tcp_timeout: str | int = "12m"  # int in m
    udp_timeout: str | int = "3m"  # int in m
    default_timeout: str | int = "10m"  # int m


class InOutboundItem(_base.SkipNoneField):
    """Base class for configuring inbound and outbound `Firewall` rules for hosts, groups, and protocols..."""

    port: int | Literal["any"] = "any"
    proto: Literal["tcp", "icmp", "udp", "any"] = "any"
    host: IPvAnyAddress | Literal["any"] = "any"
    # Inbound only?
    groups: Optional[List[str]] = None
    group: Optional[str] = None
    local_cidr: Optional[NetworkIPRange] = None
    _skip = ["groups", "group", "groups", "local_cidr"]


class Firewall(BaseModel):
    """Nebula network [firewall rules configuration](https://nebula.definmed.net/docs/config/firewall)"""

    outbound_action: Literal["drop", "reject"] = "drop"
    inbound_action: Literal["drop", "reject"] = "drop"
    default_local_cidr_any: bool = False
    conntrack: Conntrack = Field(default=Conntrack())
    outbound: List[InOutboundItem] = Field(default=InOutboundItem())
    inbound: List[InOutboundItem] = Field(default=InOutboundItem())


# class StaticHostMap(BaseModel):
# field_192_168_100_1: List[str] = Field(..., alias="192.168.100.1")
# field_nebula_ip_: List[str] = Field(..., alias="{nebula ip}")


class StaticHostMap(_base.AddressMapping):
    """Static Host Map"""

    contents: dict[IPvAnyAddress, list[RoutableIPPort]] = {}


# class CalculatedRemote(BaseModel):
# field_10_0_10_0_24: List[Field10010024Item] = Field(..., alias="10.0.10.0/24")


class CalculatedRemote(_base.AddressMapping):
    """Calculated remote"""

    contents: dict[NetworkIPRange, list[RoutableIPPort]] = {}


# class RemoteAllowList(BaseModel):
#     field_172_16_0_0_12: bool = Field(..., alias="172.16.0.0/12")
#     field_0_0_0_0_0: bool = Field(..., alias="0.0.0.0/0")
#     field_10_0_0_0_8: bool = Field(..., alias="10.0.0.0/8")
#     field_10_42_42_0_24: bool = Field(..., alias="10.42.42.0/24")


class RemoteAllowList(_base.AddressMapping):
    """Remote Allow list"""

    contents: dict[NetworkIPRange, bool | None]


# class RemoteAllowRanges(BaseModel):
#     field_10_42_42_0_24: None = Field(..., alias="10.42.42.0/24")
#     field_192_168_0_0_16: bool = Field(..., alias="192.168.0.0/16")


class RemoteAllowRanges(_base.AddressMapping):
    """Remote Allow ranges"""

    contents: dict[NetworkIPRange, bool | None]


class NebulaConfig(_base.SkipNoneField):
    """Encapsulation of [Nebula node configuration](https://nebula.defined.net/docs/config)

    Example of minimum configuration for a Nebula node

    ```python
    pki = Pki(
        ca="ca.key",
        cert="mynode.crt",
        key="mynode.key",
    )
    shm = StaticHostMap(
            contents=dict([(lighthouse.ip, [lighthouse.public])])
    )
    config = NebulaConfig(
        pki=pki,
        static_host_map=shm,
    )
    ```

    The fields `logging`, `stats` and `preferred_ranges` are not serialized to YAML if they are None.
    """

    pki: Pki
    static_host_map: StaticHostMap = Field(default=StaticHostMap())
    static_map: StaticMap = Field(default=StaticMap())
    lighthouse: Lighthouse = Field(default=Lighthouse())
    listen: Listen = Field(default=Listen())
    routines: int = Field(default=1)
    punchy: Punchy = Field(default=Punchy())
    cipher: Literal["aes", "chachapoly"] = "aes"
    preferred_ranges: List[NetworkIPRange] | None = None
    sshd: Sshd | None = Field(default=Sshd())
    relay: Relay | None = Field(default=Relay())
    tun: Tun = Field(default=Tun())
    logging: Logging | None = None
    stats: Stats | None = None
    message_metrics: bool = False
    lighthouse_metrics: bool = False
    handshakes: Handshakes = Field(default=Handshakes())
    query_buffer: int = 64
    trigger_buffer: int = 64
    tunnels: Tunnels = Field(default=Tunnels())
    firewall: Firewall = Field(default=Firewall())
    _skip = ["logging", "stats", "preferred_ranges"]

    # def model_dump(self) -> dict[str, str]:
    # out_dict = do_skip_none(self)
    # shm_dict = {}
    # for host in self.static_host_map.keys():
    #     routablelst = self.static_host_map[host]
    # shm_dict[str(host)] = [str(n) for n in routablelst]
    # out_dict["static_host_map"] = shm_dict
    # return out_dict
