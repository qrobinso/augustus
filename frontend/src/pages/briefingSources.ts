export interface BriefingSource {
  title?: string;
  url?: string;
  source?: string;
  found_by?: string[];
}

/** Group sources by each host listed in found_by. Sources with no found_by are omitted. */
export function groupSourcesByHost(
  sources: BriefingSource[]
): Record<string, BriefingSource[]> {
  const groups: Record<string, BriefingSource[]> = {};
  for (const src of sources) {
    for (const host of src.found_by ?? []) {
      (groups[host] ??= []).push(src);
    }
  }
  return groups;
}
