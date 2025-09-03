"""Base models for specifying particular serialization paradigms."""

from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_serializer,
    model_serializer,
)

CIDRLiteral = Literal[
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
]
"""Network [CIDR](https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing) range integer"""


def _do_skip_none(datacls):
    out_dict = {}
    for f in datacls:
        if (f[1] is not None) or (f[0] not in datacls._skip):
            out_dict[f[0]] = f[1]
    return out_dict


class SkipNoneField(BaseModel):
    """Base class Pydantic model that will skip None fields during serialization to YAML

    `_skip` field is a list of class fields that are allowed to be skipped during serialization if set to None.
    """

    _skip: List[str] = []

    @model_serializer
    def model_skip_none(self) -> dict[str, Any]:
        return _do_skip_none(self)


class AddressMapping(BaseModel):
    """
    Base class Pydantic model to provide serialization for various IP address types in models and nested models.

    """

    contents: Dict

    @model_serializer
    def addrs_to_strs(self) -> Dict[str, str | list[str]]:
        if len(self.contents) > 0:
            out_dict = {}
            for k in self.contents.keys():
                if type(self.contents[k]) is list:
                    c = [str(e) for e in self.contents[k]]
                else:
                    c = str(self.contents[k])
                out_dict[str(k)] = c
            return out_dict
