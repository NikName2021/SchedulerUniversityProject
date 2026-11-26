const COMPOSITE_GROUP_MARKERS = /[()[\]{},;|+]/u;
const SUBGROUP_SUFFIX =
  /(?:\s*\((?:[LlЛл]\s*([1-9][0-9]*)|([AaАаBbБбВвCcСс]))\)|\/\s*(?:[LlЛл]\s*([1-9][0-9]*)|([AaАаBbБбВвCcСс])))\s*$/u;
const GROUP_SEPARATOR = /\s*[,;|+]\s*/u;
const LETTER_SUBGROUPS: Readonly<Record<string, string>> = {
  a: "L1",
  а: "L1",
  b: "L2",
  б: "L2",
  в: "L2",
  c: "L3",
  с: "L3",
};

export type KnownSubgroups = ReadonlyMap<string, ReadonlySet<string>>;

export function getSubgroupCode(groupName: string): string | null {
  const match = groupName.trim().match(SUBGROUP_SUFFIX);
  if (!match) return null;
  const number = match[1] || match[3];
  const letter = match[2] || match[4];
  return number ? `L${number}` : LETTER_SUBGROUPS[letter.toLowerCase()];
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
    normalizedName.length > 0 &&
    !COMPOSITE_GROUP_MARKERS.test(normalizedName) &&
    getSubgroupCode(normalizedName) === null
  );
}

export function getStandaloneGroups(groups: string[]): string[] {
  return groups.filter(isStandaloneGroupName);
}
