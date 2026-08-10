import {
  TATVA_SERVICES,
  type ProjectSummary,
  type TatvaService,
} from "@/lib/project-types";

export type ProjectListFilter = {
  /** Matches quote/project code, title, service name, or brief. */
  query: string;
  /** Tatva service id, or empty for all. */
  serviceId: string;
};

function normalize(value: string | undefined | null): string {
  return (value ?? "").trim().toLowerCase();
}

export function filterProjects(
  projects: ProjectSummary[],
  filter: ProjectListFilter
): ProjectSummary[] {
  const q = normalize(filter.query);
  const serviceId = filter.serviceId.trim();

  return projects.filter((project) => {
    if (serviceId && project.service.id !== serviceId) {
      return false;
    }
    if (!q) return true;

    const haystack = [
      project.projectCode,
      project.title,
      project.brief,
      project.service.name,
      project.service.id,
      project.clientName,
    ]
      .map(normalize)
      .join(" ");

    return haystack.includes(q);
  });
}

/** Distinct services present in the loaded project list. */
export function uniqueServicesFromProjects(
  projects: ProjectSummary[]
): TatvaService[] {
  const map = new Map<string, TatvaService>();
  for (const p of projects) {
    if (!p.service?.id) continue;
    if (!map.has(p.service.id)) {
      map.set(p.service.id, p.service);
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    a.name.localeCompare(b.name)
  );
}

/** Full TatvaOps catalog for the filter dropdown, plus any unknown services in data. */
export function serviceOptionsForFilter(
  projects: ProjectSummary[]
): TatvaService[] {
  const map = new Map<string, TatvaService>();
  for (const svc of TATVA_SERVICES) {
    map.set(svc.id, svc);
  }
  for (const svc of uniqueServicesFromProjects(projects)) {
    if (!map.has(svc.id)) map.set(svc.id, svc);
  }
  return Array.from(map.values());
}
