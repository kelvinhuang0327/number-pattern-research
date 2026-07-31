from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScenarioAgent:
    name: str
    role: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    description: str = ""


@dataclass
class ScenarioGraph:
    nodes: list[ScenarioAgent] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def add_agent(self, agent: ScenarioAgent) -> None:
        self.nodes.append(agent)

    def add_edge(self, src: str, dst: str) -> None:
        self.edges.append((src, dst))

    def adjacency(self) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {node.name: [] for node in self.nodes}
        for src, dst in self.edges:
            graph.setdefault(src, []).append(dst)
        return graph
