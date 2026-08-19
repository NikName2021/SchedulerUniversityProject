const COMPOSITE_GROUP_MARKERS = /[()[\]{},;|+]/u;
const SUBGROUP_SUFFIX = /\s*\([LlЛл]\s*[12]\)\s*$/u;
const GROUP_SEPARATOR = /\s*[,;|+]\s*/u;

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

export function isStandaloneGroupName(groupName: string): boolean {
  const normalizedName = groupName.trim();
  return (
    normalizedName.length > 0 && !COMPOSITE_GROUP_MARKERS.test(normalizedName)
  );
}

export function getStandaloneGroups(groups: string[]): string[] {
  return groups.filter(isStandaloneGroupName);
}
