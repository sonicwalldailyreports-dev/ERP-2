import { apiClient } from "./apiClient";
import type { Branch, Company } from "../types/organization";

export const organizationApi = {
  companies: () => apiClient<Company[]>("/companies"),
  createCompany: (input: { name: string; code: string }) => apiClient<Company>("/companies", { method: "POST", body: JSON.stringify(input) }),
  updateCompany: (id: string, input: { name?: string; code?: string }) => apiClient<Company>(`/companies/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setCompanyActive: (id: string, active: boolean) => apiClient<Company>(`/companies/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
  branches: (companyId: string) => apiClient<Branch[]>(`/companies/${companyId}/branches`),
  createBranch: (input: { company_id: string; name: string; code: string }) => apiClient<Branch>(`/companies/${input.company_id}/branches`, { method: "POST", body: JSON.stringify(input) }),
  updateBranch: (companyId: string, id: string, input: { name?: string; code?: string }) => apiClient<Branch>(`/companies/${companyId}/branches/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setBranchActive: (companyId: string, id: string, active: boolean) => apiClient<Branch>(`/companies/${companyId}/branches/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
};
