import { apiClient } from "./apiClient";
import type { ManagedUser, PermissionSummary, UserListResponse, BranchAssignment } from "../types/users";

type UserInput = {
  username: string; email: string; full_name: string; phone?: string;
  password?: string; company_ids: string[]; branch_assignments: BranchAssignment[]; role_ids: string[];
};

export const usersApi = {
  list: (params: { companyId?: string; branchId?: string; search?: string; status?: string; page?: number; pageSize?: number }) => {
    const query = new URLSearchParams();
    if (params.companyId) query.set("company_id", params.companyId);
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status_filter", params.status);
    query.set("page", String(params.page ?? 1)); query.set("page_size", String(params.pageSize ?? 25));
    return apiClient<UserListResponse>(`/users?${query}`);
  },
  create: (input: UserInput) => apiClient<ManagedUser>(`/users${input.company_ids[0] ? `?company_id=${encodeURIComponent(input.company_ids[0])}` : ""}`, { method: "POST", body: JSON.stringify(input) }),
  update: (id: string, input: Partial<UserInput> & { status?: string; is_active?: boolean }) =>
    apiClient<ManagedUser>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setActive: (id: string, active: boolean) => apiClient<ManagedUser>(`/users/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
  resetPassword: (id: string, newPassword?: string) =>
    apiClient<{ message: string; temporary_password?: string }>(`/users/${id}/reset-password`, { method: "POST", body: JSON.stringify(newPassword ? { new_password: newPassword } : {}) }),
  permissions: (id: string) => apiClient<PermissionSummary>(`/users/${id}/permissions-summary`),
  loginHistory: (id: string) => apiClient<unknown[]>(`/users/${id}/login-history`),
  auditActivity: (id: string) => apiClient<unknown[]>(`/users/${id}/audit-activity`),
};
