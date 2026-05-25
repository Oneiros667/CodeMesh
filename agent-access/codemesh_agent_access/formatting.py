from __future__ import annotations

from typing import Any


_RELATIONSHIP_GROUP_LABELS = {
    "defines": "Defines",
    "contains": "Contains",
    "callers": "Callers",
    "callees": "Callees",
    "writes": "Writes",
    "reads": "Reads",
    "uses_types": "Uses types",
}


def format_context_package_for_agent(package: dict[str, Any]) -> str:
    query = package.get("query") if isinstance(package.get("query"), dict) else {}
    repository = package.get("repository") if isinstance(package.get("repository"), dict) else None
    latest_run = package.get("latest_run") if isinstance(package.get("latest_run"), dict) else None
    items = package.get("items") if isinstance(package.get("items"), list) else []

    lines = [
        "CodeMesh context package",
        f"Query: {_value(query.get('query'))}",
    ]
    if repository:
        lines.append(f"Repository: {_value(repository.get('repository_id'))} ({_value(repository.get('root_path'))})")
    if latest_run:
        lines.append(f"Latest run: {_value(latest_run.get('run_id'))} {_value(latest_run.get('stage'))}")
    lines.append(f"Items: {len(items)}")

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        hit = item.get("hit") if isinstance(item.get("hit"), dict) else {}
        node = item.get("node") if isinstance(item.get("node"), dict) else {}
        span = node.get("span") if isinstance(node.get("span"), dict) else {}
        rationale = item.get("rationale") if isinstance(item.get("rationale"), dict) else {}

        lines.extend(
            [
                "",
                f"{index}. {_node_title(hit, node)}",
                f"   File: {_span_location(hit, span)}",
                f"   Node: {_value(hit.get('node_id') or node.get('id'))}",
                f"   Score: {_score(hit.get('score'))}; rank {rationale.get('rank', index)}",
            ]
        )

        content = item.get("content") if isinstance(item.get("content"), dict) else None
        if content and content.get("hash"):
            lines.append(f"   Content hash: {_value(content.get('hash'))}")

        group_lines = _relationship_lines(item.get("relationship_groups"))
        if group_lines:
            lines.append("   Relationships:")
            lines.extend(group_lines)

        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            lines.append("   Snippet:")
            lines.extend(f"     {line}" for line in snippet.splitlines())

    return "\n".join(lines)


def _node_title(hit: dict[str, Any], node: dict[str, Any]) -> str:
    kind = _value(hit.get("kind") or node.get("kind"))
    name = _value(node.get("name") or hit.get("stable_key") or hit.get("node_id"))
    return f"{kind} {name}"


def _span_location(hit: dict[str, Any], span: dict[str, Any]) -> str:
    file_path = _value(hit.get("file_path") or span.get("file_path"))
    start_line = _line_number(hit.get("start_line") or span.get("start_line"))
    end_line = _line_number(hit.get("end_line") or span.get("end_line"))
    if start_line and end_line and start_line != end_line:
        return f"{file_path}:{start_line}-{end_line}"
    if start_line:
        return f"{file_path}:{start_line}"
    return file_path


def _relationship_lines(groups: Any) -> list[str]:
    if not isinstance(groups, dict):
        return []

    lines = []
    for group, label in _RELATIONSHIP_GROUP_LABELS.items():
        relationships = groups.get(group)
        if not isinstance(relationships, list) or not relationships:
            continue

        refs = [_relationship_ref(relationship) for relationship in relationships if isinstance(relationship, dict)]
        refs = [ref for ref in refs if ref]
        if refs:
            lines.append(f"     {label}: {'; '.join(refs)}")

    return lines


def _relationship_ref(relationship: dict[str, Any]) -> str:
    other = relationship.get("other") if isinstance(relationship.get("other"), dict) else {}
    name = _value(other.get("name") or other.get("node_id"))
    kind = _value(other.get("kind"))
    location = _relationship_location(other)
    direction = _value(relationship.get("direction"))
    return f"{name} ({kind}, {direction}, {location})"


def _relationship_location(other: dict[str, Any]) -> str:
    file_path = _value(other.get("file_path"))
    start_line = _line_number(other.get("start_line"))
    end_line = _line_number(other.get("end_line"))
    if start_line and end_line and start_line != end_line:
        return f"{file_path}:{start_line}-{end_line}"
    if start_line:
        return f"{file_path}:{start_line}"
    return file_path


def _value(value: Any) -> str:
    text = str(value or "").strip()
    return text or "-"


def _line_number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _score(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "0.000"
