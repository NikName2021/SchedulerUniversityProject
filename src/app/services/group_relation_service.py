from __future__ import annotations

import re
from dataclasses import dataclass

SUBGROUP_SUFFIX = re.compile(r"\s*\(([LlЛл])\s*([12])\)\s*$")
GROUP_SEPARATOR = re.compile(r"\s*[,;|+]\s*")


@dataclass(frozen=True)
class ParsedGroupLabel:
    label: str
    base_groups: tuple[str, ...]
    subgroup: str | None

    @property
    def is_joint(self) -> bool:
        return len(self.base_groups) > 1

    @property
    def is_standalone(self) -> bool:
        return len(self.base_groups) == 1 and self.subgroup is None


def parse_group_label(label: str) -> ParsedGroupLabel:
    normalized = " ".join(str(label or "").strip().split())
    subgroup: str | None = None
    match = SUBGROUP_SUFFIX.search(normalized)
    if match:
        subgroup = f"L{match.group(2)}"
        normalized_without_suffix = normalized[: match.start()].strip()
    else:
        normalized_without_suffix = normalized

    base_groups = tuple(
        dict.fromkeys(
            item.strip()
            for item in GROUP_SEPARATOR.split(normalized_without_suffix)
            if item.strip()
        )
    )
    return ParsedGroupLabel(
        label=normalized,
        base_groups=base_groups,
        subgroup=subgroup,
    )


def collect_known_subgroups(labels: list[str] | set[str]) -> dict[str, set[str]]:
    known: dict[str, set[str]] = {}
    for label in labels:
        parsed = parse_group_label(label)
        if not parsed.subgroup:
            continue
        for base_group in parsed.base_groups:
            known.setdefault(base_group, set()).add(parsed.subgroup)
    return known


def group_resource_keys(
    label: str,
    known_subgroups: dict[str, set[str]],
) -> set[str]:
    parsed = parse_group_label(label)
    resources: set[str] = set()
    for base_group in parsed.base_groups:
        if parsed.subgroup:
            resources.add(f"{base_group}::{parsed.subgroup}")
            continue
        subgroups = known_subgroups.get(base_group)
        if subgroups:
            resources.update(f"{base_group}::{code}" for code in subgroups)
        else:
            resources.add(f"{base_group}::*")
    return resources


def labels_overlap(
    left: str,
    right: str,
    known_subgroups: dict[str, set[str]],
) -> bool:
    return bool(
        group_resource_keys(left, known_subgroups)
        & group_resource_keys(right, known_subgroups)
    )


def expand_group_selection(
    requested_labels: list[str],
    available_labels: list[str],
) -> dict[str, list[str]]:
    parsed_available = {
        label: parse_group_label(label)
        for label in dict.fromkeys(available_labels)
        if parse_group_label(label).base_groups
    }
    selected_base_groups = {
        base_group
        for label in requested_labels
        for base_group in parse_group_label(label).base_groups
    }

    changed = True
    while changed:
        changed = False
        for parsed in parsed_available.values():
            if selected_base_groups.intersection(parsed.base_groups):
                previous_size = len(selected_base_groups)
                selected_base_groups.update(parsed.base_groups)
                changed = changed or len(selected_base_groups) != previous_size

    selected_labels = sorted(
        label
        for label, parsed in parsed_available.items()
        if selected_base_groups.intersection(parsed.base_groups)
    )
    joint_groups = sorted(
        label
        for label in selected_labels
        if parsed_available[label].is_joint
        and parsed_available[label].subgroup is None
    )
    subgroup_groups = sorted(
        label for label in selected_labels if parsed_available[label].subgroup
    )
    return {
        "base_groups": sorted(selected_base_groups),
        "selected_groups": selected_labels,
        "joint_groups": joint_groups,
        "subgroup_groups": subgroup_groups,
    }
