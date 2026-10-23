"""Relationship map utilities for RUMOURPRINT.

Edges encode similarity between SUBMITTED documents, not actual sharing,
transmission direction, source attribution, dates, virality or truth.
Pure functions for safe, repeatable graph construction.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from html import escape
from math import cos, pi, sin
from typing import Any

PALETTE = ("#28695C", "#566A85", "#A17B42", "#876C8D", "#627A54", "#88665D", "#527D86", "#647078")


def build_network(items: list[dict], matrix: list[list[float]], threshold: float) -> dict:
    """Return positioned nodes / edges and components using 0-based indices."""
    n = len(items)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("Similarity matrix does not match the number of messages")
    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between zero and one")
    edges = []
    neighbors = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            strength = float(matrix[i][j])
            if strength >= threshold:
                edges.append({"source": i, "target": j, "weight": round(strength, 4)})
                neighbors[i].add(j)
                neighbors[j].add(i)
    seen = set()
    components = []
    for i in range(n):
        if i in seen:
            continue
        stack = [i]
        seen.add(i)
        group = []
        while stack:
            cur = stack.pop()
            group.append(cur)
            for neighbor in sorted(neighbors[cur]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(group))
    components.sort(key=lambda component: (-len(component), component[0]))
    positions = {}
    nodes = []
    columns = 3 if len(components) > 2 else max(1, len(components))
    for g, group in enumerate(components):
        center_x = (g % columns) * 5.5
        center_y = -(g // columns) * 5.0
        radius = min(1.65, max(.8, .35 * len(group)))
        for k, index in enumerate(group):
            angle = (2 * pi * k / len(group)) - pi / 2 if len(group) > 1 else 0
            x = center_x + (radius * cos(angle) if len(group) > 1 else 0)
            y = center_y + (radius * sin(angle) if len(group) > 1 else 0)
            positions[index] = (round(x, 3), round(y, 3))
            nodes.append({
                "index": index,
                "group": g,
                "color": PALETTE[g % len(PALETTE)],
                "x": positions[index][0],
                "y": positions[index][1],
                "degree": len(neighbors[index]),
            })
    nodes.sort(key=lambda node: node["index"])
    return {"nodes": nodes, "edges": edges, "components": components}


def highlight_differences(previous: str, current: str) -> tuple[str, str]:
    """Escape all source strings and mark additions/deletions for review."""
    import re
    a = re.findall(r"\S+|\s+", previous)
    b = re.findall(r"\S+|\s+", current)
    old, new = [], []
    for op, a1, a2, b1, b2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            segment = escape("".join(a[a1:a2]))
            old.append(segment)
            new.append(segment)
        else:
            if op in ("delete", "replace"):
                old.append(f'<mark class="rp-diff-remove">{escape("".join(a[a1:a2]))}</mark>')
            if op in ("insert", "replace"):
                new.append(f'<mark class="rp-diff-add">{escape("".join(b[b1:b2]))}</mark>')
    return "".join(old), "".join(new)


def figure_for_network(graph: dict, items: list[dict]):
    """Build Plotly diagram; imports Plotly lazily for engine-only test usage."""
    import plotly.graph_objects as go
    edge_x, edge_y = [], []
    positions = {node["index"]: (node["x"], node["y"]) for node in graph["nodes"]}
    for e in graph["edges"]:
        x0, y0 = positions[e["source"]]
        x1, y1 = positions[e["target"]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines", line=dict(width=1.6, color="#B4C5BE"),
        hoverinfo="skip", showlegend=False, name="Candidate relationships"
    ))
    for group_id, group in enumerate(graph["components"]):
        series = [node for node in graph["nodes"] if node["group"] == group_id]
        custom = []
        for node in series:
            item = items[node["index"]]
            preview = str(item.get("text", ""))[:195]
            if len(str(item.get("text", ""))) > 195:
                preview += "…"
            custom.append((node["index"] + 1, escape(str(item.get("source", "Unknown"))), escape(preview), node["degree"]))
        fig.add_trace(go.Scatter(
            x=[node["x"] for node in series], y=[node["y"] for node in series],
            mode="markers+text", text=[f"{node['index']+1:02d}" for node in series],
            textposition="middle center", textfont=dict(color="white", size=12, family="Arial"),
            marker=dict(size=44, color=series[0]["color"], line=dict(width=2, color="#FFFFFF")),
            customdata=custom,
            hovertemplate="<b>Claim #%{customdata[0]}</b><br>Source: %{customdata[1]}<br>Linked messages: %{customdata[3]}<br>%{customdata[2]}<extra></extra>",
            name=f"Group {group_id+1}", showlegend=False,
        ))
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", font=dict(family="Segoe UI, Arial"),
        margin=dict(l=20, r=20, t=25, b=20), height=535,
        xaxis=dict(visible=False, fixedrange=True), yaxis=dict(visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),
        dragmode="pan", hoverlabel=dict(bgcolor="white", font_size=12, font_color="#223B35"),
    )
    return fig
