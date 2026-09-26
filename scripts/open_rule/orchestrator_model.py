"""Orchestrator data model."""

from __future__ import annotations

from dataclasses import dataclass
import re

from scripts.open_rule.loader import Cluster
from scripts.open_rule.matcher import Decision
from scripts.open_rule.objects import StagedObjects


TICKET_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SEVERITY = {
    "ERROR": 80,
    "SHADOWED": 70,
    "SHADOW_UNKNOWN": 60,
    "MANUAL_F5": 50,
    "CREATE": 40,
    "EXTEND": 30,
    "ALREADY_OPEN": 20,
    "INTRA_SEGMENT": 10,
}


@dataclass(frozen=True)
class HopVerdict:
    firewall: str
    vendor: str
    cluster: str
    in_segment: str
    out_segment: str
    in_zone: str
    out_zone: str
    decision: Decision


@dataclass(frozen=True)
class FlowResult:
    ticket: str
    src: str
    dst: str
    proto: str
    port: str
    src_segment: str | None
    dst_segment: str | None
    path: tuple[str, ...]
    hops: tuple[HopVerdict, ...]
    status: str
    error: str | None = None


ClusterCache = dict[str, tuple[Cluster, StagedObjects]]
