import { apiClient } from "./apiClient";
import type { Customer, CustomerListResponse } from "../types/customers";

export type CustomerInput = {
  customer_code: string;
  name?: string | null;
  customer_name?: string | null;
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

export const customersApi = {
  list: (params: { companyId: string; branchId?: string; search?: string; status?: string; page?: number; pageSize?: number }) => {
    const query = new URLSearchParams({ company_id: params.companyId });
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.pageSize ?? 25));
    return apiClient<CustomerListResponse>(`/customers?${query}`);
  },
  create: (companyId: string, branchId: string | undefined, input: CustomerInput) => {
    const query = new URLSearchParams({ company_id: companyId });
    if (branchId) query.set("branch_id", branchId);
    return apiClient<Customer>(`/customers?${query}`, { method: "POST", body: JSON.stringify(input) });
  },
  get: (id: string) => apiClient<Customer>(`/customers/${id}`),
  update: (id: string, input: Partial<CustomerInput> & { status?: string; is_active?: boolean }) =>
    apiClient<Customer>(`/customers/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setActive: (id: string, active: boolean) =>
    apiClient<Customer>(`/customers/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
  remove: (id: string) => apiClient<Customer>(`/customers/${id}`, { method: "DELETE" }),
};
