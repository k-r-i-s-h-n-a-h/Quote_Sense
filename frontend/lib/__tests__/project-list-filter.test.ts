import { describe, expect, it } from "vitest";
import {
  filterProjects,
  serviceOptionsForFilter,
  uniqueServicesFromProjects,
} from "../project-list-filter";
import { TATVA_SERVICES, type ProjectSummary } from "../project-types";

function summary(
  overrides: Partial<ProjectSummary> & Pick<ProjectSummary, "id" | "projectCode">
): ProjectSummary {
  return {
    title: "Sample",
    service: { id: "construction", name: "Residential Construction", icon: "🏗️" },
    clientName: "Client",
    status: "quotes_received",
    brief: "A brief",
    vendorCount: 1,
    quoteCount: 1,
    finalizedQuoteCount: 0,
    updatedAt: "—",
    ...overrides,
  };
}

describe("project-list-filter", () => {
  const projects = [
    summary({
      id: "1",
      projectCode: "0F4530",
      title: "Residential Construction — 0F4530",
      service: { id: "construction", name: "Residential Construction", icon: "🏗️" },
    }),
    summary({
      id: "2",
      projectCode: "0F452E",
      title: "Residential Interiors — 0F452E",
      service: { id: "interior", name: "Residential Interiors", icon: "🛋️" },
      brief: "3 BHK apartment",
    }),
  ];

  it("filters by quote/project code", () => {
    const out = filterProjects(projects, { query: "0f4530", serviceId: "" });
    expect(out).toHaveLength(1);
    expect(out[0].projectCode).toBe("0F4530");
  });

  it("filters by service id", () => {
    const out = filterProjects(projects, { query: "", serviceId: "interior" });
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("2");
  });

  it("combines query and service filter", () => {
    const out = filterProjects(projects, {
      query: "interior",
      serviceId: "construction",
    });
    expect(out).toHaveLength(0);
  });

  it("lists unique services sorted by name", () => {
    const services = uniqueServicesFromProjects(projects);
    expect(services.map((s) => s.id)).toEqual(["construction", "interior"]);
  });

  it("filter dropdown includes full TatvaOps catalog", () => {
    const options = serviceOptionsForFilter(projects);
    expect(options.length).toBeGreaterThanOrEqual(TATVA_SERVICES.length);
    expect(options.map((s) => s.id)).toEqual(
      expect.arrayContaining(TATVA_SERVICES.map((s) => s.id))
    );
  });
});
