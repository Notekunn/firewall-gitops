"""Render rule opener results."""

from __future__ import annotations

from typing import Any

import yaml

from scripts.open_rule.matcher import Decision
from scripts.open_rule.orchestrator import FlowResult, HopVerdict


CAVEAT_TEXT = {
    "shadow_unverified": "not full-shadow-checked; verify preceding denies and rule placement",
    "assumed_path": "path auto-computed from topology.yaml; verify routing/NAT",
    "intrazone_likely_permitted": "likely permitted by intrazone-default; verify",
    "src_after_f5_unverified": "source may be F5-SNAT; verify real source before applying",
    "fortinet_reset_deploys_accept": "FortiGate reset-* maps to accept in module; verify",
}


def render_text(results: list[FlowResult]) -> str:
    return "\n\n".join(_render_flow(result) for result in results)


def render_json(results: list[FlowResult]) -> list[dict[str, Any]]:
    return [_flow_to_dict(result) for result in results]


def yaml_for_decision(decision: Decision) -> str:
    payload: dict[str, Any] = {}
    if decision.new_addresses:
        payload["addresses"] = list(decision.new_addresses)
    if decision.new_services:
        payload["services"] = list(decision.new_services)
    if decision.proposed_rule:
        payload["rules"] = [decision.proposed_rule]
    if not payload:
        return ""
    return yaml.safe_dump(payload, sort_keys=False)


def _render_flow(result: FlowResult) -> str:
    lines = [
        f"ticket: {result.ticket}",
        f"flow: {result.src} -> {result.dst} {result.proto}/{result.port}",
        f"segments: {result.src_segment or '?'} -> {result.dst_segment or '?'}",
        f"assumed path: {' -> '.join(result.path) if result.path else '(none)'}",
        f"status: {result.status}",
    ]
    if result.error:
        lines.append(f"error: {result.error}")
        return "\n".join(lines)

    for hop in result.hops:
        lines.extend(_render_hop(hop))
    return "\n".join(lines)


def _render_hop(hop: HopVerdict) -> list[str]:
    decision = hop.decision
    title = (
        f"- firewall: {hop.firewall or 'intra-segment'}"
        f" ({hop.vendor or 'none'}) verdict={decision.verdict}"
    )
    lines = [title]
    if hop.firewall:
        lines.append(
            f"  path: {hop.in_segment}/{hop.in_zone} -> "
            f"{hop.out_segment}/{hop.out_zone}"
        )
    if decision.rule_name:
        lines.append(f"  rule: {decision.rule_name}")
    if decision.rule_sources:
        lines.append(f"  source: {', '.join(decision.rule_sources)}")
        if len(decision.rule_sources) > 1:
            lines.append("  warn: duplicate rule name; verify target file")
    if decision.file_hint:
        lines.append(f"  suggested file: {decision.file_hint}")
    if decision.position:
        where = decision.position.get("where", "last")
        pivot = decision.position.get("pivot")
        suffix = f" {pivot}" if pivot else ""
        lines.append(f"  position: {where}{suffix}")
    if decision.dim:
        lines.append(f"  extend: {decision.dim}")
    if decision.message:
        lines.append(f"  note: {decision.message}")
    for caveat in decision.caveats:
        lines.append(f"  caveat: {CAVEAT_TEXT.get(caveat, caveat)}")

    snippet = yaml_for_decision(decision)
    if snippet:
        lines.append("  proposed YAML:")
        lines.extend(f"    {line}" for line in snippet.rstrip().splitlines())
    return lines


def _flow_to_dict(result: FlowResult) -> dict[str, Any]:
    return {
        "ticket": result.ticket,
        "src": result.src,
        "dst": result.dst,
        "proto": result.proto,
        "port": result.port,
        "src_segment": result.src_segment,
        "dst_segment": result.dst_segment,
        "path": list(result.path),
        "status": result.status,
        "error": result.error,
        "hops": [_hop_to_dict(hop) for hop in result.hops],
    }


def _hop_to_dict(hop: HopVerdict) -> dict[str, Any]:
    decision = hop.decision
    return {
        "firewall": hop.firewall,
        "vendor": hop.vendor,
        "cluster": hop.cluster,
        "in_segment": hop.in_segment,
        "out_segment": hop.out_segment,
        "in_zone": hop.in_zone,
        "out_zone": hop.out_zone,
        "verdict": decision.verdict,
        "rule_name": decision.rule_name,
        "rule_sources": list(decision.rule_sources),
        "dim": decision.dim,
        "new_addresses": list(decision.new_addresses),
        "new_services": list(decision.new_services),
        "proposed_rule": decision.proposed_rule,
        "caveats": list(decision.caveats),
        "message": decision.message,
        "file_hint": decision.file_hint,
        "position": decision.position,
    }
