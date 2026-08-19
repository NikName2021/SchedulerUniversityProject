const COMPOSITE_GROUP_MARKERS = /[()[\]{},;|+]/u;
const SUBGROUP_SUFFIX = /\s*\([LlЛл]\s*([12])\)\s*$/u;
const GROUP_SEPARATOR = /\s*[,;|+]\s*/u;

export type KnownSubgroups = ReadonlyMap<string, ReadonlySet<string>>;

export function getSubgroupCode(groupName: string): string | null {
  const match = groupName.trim().match(SUBGROUP_SUFFIX);
  return match ? `L${match[1]}` : null;
}

export function getBaseGroupNames(groupName: string): string[] {
  return groupName
    .trim()
    .replace(SUBGROUP_SUFFIX, "")
    .split(GROUP_SEPARATOR)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function groupLabelIncludesBase(
  groupLabel: string,
  baseGroup: string,
): boolean {
  return getBaseGroupNames(groupLabel).includes(baseGroup);
}

export function collectKnownSubgroups(groupNames: string[]): KnownSubgroups {
  const known = new Map<string, Set<string>>();
  groupNames.forEach((groupName) => {
    const subgroup = getSubgroupCode(groupName);
    if (!subgroup) return;
    getBaseGroupNames(groupName).forEach((baseGroup) => {
      const subgroups = known.get(baseGroup) || new Set<string>();
      subgroups.add(subgroup);
      known.set(baseGroup, subgroups);
    });
  });
  return known;
}

function getGroupResourceKeys(
  groupName: string,
  knownSubgroups: KnownSubgroups,
): Set<string> {
  const subgroup = getSubgroupCode(groupName);
  const resources = new Set<string>();
  getBaseGroupNames(groupName).forEach((baseGroup) => {
    if (subgroup) {
      resources.add(`${baseGroup}::${subgroup}`);
      return;
    }
    const subgroups = knownSubgroups.get(baseGroup);
    if (subgroups?.size) {
      subgroups.forEach((code) => resources.add(`${baseGroup}::${code}`));
    } else {
      resources.add(`${baseGroup}::*`);
    }
  });
  return resources;
}

export function groupLabelsOverlap(
  left: string,
  right: string,
  knownSubgroups: KnownSubgroups,
): boolean {
  const leftResources = getGroupResourceKeys(left, knownSubgroups);
  return Array.from(getGroupResourceKeys(right, knownSubgroups)).some(
    (resource) => leftResources.has(resource),
  );
}

export function isStandaloneGroupName(groupName: string): boolean {
  const normalizedName = groupName.trim();
  return (
    normalizedName.length > 0 && !COMPOSITE_GROUP_MARKERS.test(normalizedName)
  );
}

export function getStandaloneGroups(groups: string[]): string[] {
  return groups.filter(isStandaloneGroupName);
}
