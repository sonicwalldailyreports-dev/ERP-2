import { apiClient } from "./apiClient";
import type { Vendor, VendorListResponse } from "../types/vendors";

export type VendorInput = {
  vendor_code: string;
  name?: string | null;
  vendor_name?: string | null;
  company_name?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  tax_id?: string | null;
  tax_number?: string | null;
  opening_balance?: string | null;
  credit_limit?: string | null;
  payment_terms?: string | null;
  notes?: string | null;
};

export const vendorsApi = {
  list: (params: { companyId: string; branchId?: string; search?: string; status?: string; page?: number; pageSize?: number }) => {
    const query = new URLSearchParams({ company_id: params.companyId });
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.pageSize ?? 25));
    return apiClient<VendorListResponse>(`/vendors?${query}`);
  },
  create: (companyId: string, branchId: string | undefined, input: VendorInput) => {
    const query = new URLSearchParams({ company_id: companyId });
    if (branchId) query.set("branch_id", branchId);
    return apiClient<Vendor>(`/vendors?${query}`, { method: "POST", body: JSON.stringify(input) });
  },
  get: (id: string) => apiClient<Vendor>(`/vendors/${id}`),
  update: (id: string, input: Partial<VendorInput> & { status?: string; is_active?: boolean }) =>
    apiClient<Vendor>(`/vendors/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setActive: (id: string, active: boolean) =>
    apiClient<Vendor>(`/vendors/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
  remove: (id: string) => apiClient<Vendor>(`/vendors/${id}`, { method: "DELETE" }),
};
