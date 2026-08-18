const COMPOSITE_GROUP_MARKERS = /[()[\]{},;|+]/u;

export function isStandaloneGroupName(groupName: string): boolean {
  const normalizedName = groupName.trim();
  return (
    normalizedName.length > 0 && !COMPOSITE_GROUP_MARKERS.test(normalizedName)
  );
}

export function getStandaloneGroups(groups: string[]): string[] {
  return groups.filter(isStandaloneGroupName);
}
