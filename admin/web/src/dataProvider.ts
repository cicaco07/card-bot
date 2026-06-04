import type { DataProvider } from "@refinedev/core";
import { requestJson } from "./rest";

function resourcePath(resource: string): string {
  return resource.replace(/^\//, "");
}

export const dataProvider: DataProvider = {
  getApiUrl: () => "",
  getList: async ({ resource, filters, pagination }) => {
    const query: Record<string, string | number | undefined> = {
      limit: pagination?.pageSize ?? 50,
    };
    for (const filter of filters ?? []) {
      if ("field" in filter && filter.operator === "eq") {
        query[filter.field] = String(filter.value);
      }
      if ("field" in filter && filter.operator === "contains") {
        query[filter.field] = String(filter.value);
      }
    }
    const data = await requestJson<any[]>(resourcePath(resource), { query });
    return { data, total: data.length };
  },
  getOne: async ({ resource, id }) => {
    const data = await requestJson<any>(`${resourcePath(resource)}/${id}`);
    return { data };
  },
  create: async () => {
    throw new Error("Create belum didukung pada admin v1.");
  },
  update: async () => {
    throw new Error("Update belum didukung pada admin v1.");
  },
  deleteOne: async () => {
    throw new Error("Delete belum didukung pada admin v1.");
  },
  custom: async ({ url, method, payload, query }) => {
    const data = await requestJson<any>(url, {
      method: method?.toUpperCase() ?? "GET",
      body: payload ? JSON.stringify(payload) : undefined,
      query: query as Record<string, string | number | undefined> | undefined,
    });
    return { data };
  },
  getMany: async () => {
    throw new Error("getMany belum dipakai pada admin v1.");
  },
  createMany: async () => {
    throw new Error("createMany belum didukung pada admin v1.");
  },
  updateMany: async () => {
    throw new Error("updateMany belum didukung pada admin v1.");
  },
  deleteMany: async () => {
    throw new Error("deleteMany belum didukung pada admin v1.");
  },
};
