import os
import re
from dataclasses import dataclass

import yaml

from .impact_models import ImpactEdge


@dataclass
class ComponentDef:
    name: str
    paths: list[str]
    depends_on: list[str]
    owners: list[str]


def load_arch_map(repo_root: str) -> dict[str, ComponentDef]:
    """
    Load arch_map.yaml from the repo root.
    Expected format:
      components:
        - name: "auth_service"
          paths: ["auth/.*", "lib/security/.*"]
          depends_on: ["db_layer"]
          owners: ["@team-auth"]
    """
    path = os.path.join(repo_root, "arch_map.yaml")
    if not os.path.isfile(path):
        return {}

    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        components = {}
        for item in data.get("components", []):
            name = item.get("name")
            if not name:
                continue

            components[name] = ComponentDef(
                name=name,
                paths=item.get("paths", []),
                depends_on=item.get("depends_on", []),
                owners=item.get("owners", []),
            )
        return components
    except Exception:
        # If parsing fails, return empty map safely
        return {}


def resolve_components(changed_paths: list[str], arch_map: dict[str, ComponentDef]) -> list[str]:
    """
    Identify which components are modified based on changed paths.
    """
    impacted_components = set()

    for comp in arch_map.values():
        for pattern in comp.paths:
            # Check if any changed path matches this component's pattern
            # Using regex for paths in arch_map as specified in requirements
            regex = re.compile(pattern)
            for path in changed_paths:
                if regex.search(path):
                    impacted_components.add(comp.name)
                    break

    return sorted(impacted_components)


def build_impact_chain(
    impacted_components: list[str], arch_map: dict[str, ComponentDef]
) -> list[ImpactEdge]:
    """
    Trace dependencies: If Component A changes, and B depends on A, then B is impacted.
    """
    edges = []

    # We look for components that depend ON the impacted components.
    # arch_map defines "depends_on" (forward dependency).
    # If A depends on B, and B changes, then A is impacted.

    for impacted in impacted_components:
        # Find who depends on 'impacted'
        for candidate in arch_map.values():
            if impacted in candidate.depends_on:
                edges.append(
                    ImpactEdge(
                        src=impacted,
                        dst=candidate.name,
                        reason=f"{candidate.name} depends on {impacted}",
                    )
                )

    return edges


def owners_from_arch_map(components: list[str], arch_map: dict[str, ComponentDef]) -> set[str]:
    owners = set()
    for name in components:
        comp = arch_map.get(name)
        if comp:
            owners.update(comp.owners)
    return owners
