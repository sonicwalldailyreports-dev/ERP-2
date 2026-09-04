import { apiClient } from "./apiClient";
import type { Permission, Role, UserPermissionOverride } from "../types/rbac";

export const rbacApi = {
  roles: (companyId?: string) =>
    apiClient<Role[]>(`/roles${companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""}`),
  permissions: () => apiClient<Permission[]>("/roles/permissions"),
  rolePermissions: (id: string) => apiClient<Permission[]>(`/roles/${id}/permissions`),
  createPermission: (input: { code: string; description?: string }) =>
    apiClient<Permission>("/roles/permissions", { method: "POST", body: JSON.stringify(input) }),
  createRole: (input: { name: string; description?: string; company_id?: string; is_system?: boolean }) =>
    apiClient<Role>("/roles", { method: "POST", body: JSON.stringify(input) }),
  updateRole: (id: string, input: { name?: string; description?: string; is_active?: boolean; status?: "active" | "inactive" }) =>
    apiClient<Role>(`/roles/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  setRolePermissions: (id: string, permission_ids: string[]) =>
    apiClient<Role>(`/roles/${id}/permissions`, { method: "PUT", body: JSON.stringify({ permission_ids }) }),
  removeRole: (userId: string, roleId: string) =>
    apiClient<void>(`/roles/users/${userId}/${roleId}`, { method: "DELETE" }),
  userRoles: (userId: string) => apiClient<Role[]>(`/roles/users/${userId}`),
  assignRole: (userId: string, roleId: string) =>
    apiClient<Role>(`/roles/users/${userId}`, { method: "POST", body: JSON.stringify({ role_id: roleId }) }),
  overrides: (userId: string) => apiClient<UserPermissionOverride[]>(`/roles/users/${userId}/overrides`),
  createOverride: (userId: string, input: { permission_id: string; company_id?: string; branch_id?: string; is_granted: boolean }) =>
    apiClient<UserPermissionOverride>(`/roles/users/${userId}/overrides`, { method: "POST", body: JSON.stringify(input) }),
  deactivateOverride: (id: string) => apiClient<void>(`/roles/overrides/${id}`, { method: "DELETE" }),
  myPermissions: (companyId?: string, branchId?: string) => {
    const query = new URLSearchParams();
    if (companyId) query.set("company_id", companyId);
    if (branchId) query.set("branch_id", branchId);
    return apiClient<string[]>(`/auth/me/permissions${query.size ? `?${query}` : ""}`);
  },
};
