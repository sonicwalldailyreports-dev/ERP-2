import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { rbacApi } from "../../services/rbacApi";

export function useRoles(companyId?: string) {
  return useQuery({ queryKey: ["roles", companyId], queryFn: () => rbacApi.roles(companyId) });
}

export function usePermissions() {
  return useQuery({ queryKey: ["permissions"], queryFn: rbacApi.permissions, staleTime: 300_000 });
}

export function useRolePermissions(roleId?: string) {
  return useQuery({
    queryKey: ["role-permissions", roleId],
    queryFn: () => rbacApi.rolePermissions(roleId as string),
    enabled: Boolean(roleId),
  });
}

export function useMyPermissions(companyId?: string, branchId?: string) {
  return useQuery({
    queryKey: ["my-permissions", companyId, branchId],
    queryFn: () => rbacApi.myPermissions(companyId, branchId),
    staleTime: 60_000,
  });
}

export function useCan(permission: string, companyId?: string, branchId?: string) {
  const query = useMyPermissions(companyId, branchId);
  return { ...query, can: query.data?.includes(permission) ?? false };
}

export function useRoleMutations(companyId?: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["roles", companyId] });
  const create = useMutation({ mutationFn: rbacApi.createRole, onSuccess: refresh });
  const update = useMutation({ mutationFn: ({ id, ...input }: { id: string; name?: string; description?: string; is_active?: boolean }) => rbacApi.updateRole(id, input), onSuccess: refresh });
  const setPermissions = useMutation({ mutationFn: ({ id, permission_ids }: { id: string; permission_ids: string[] }) => rbacApi.setRolePermissions(id, permission_ids), onSuccess: refresh });
  return { create, update, setPermissions };
}

export function useUserRoleMutations(userId: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["user-roles", userId] });
  const roles = useQuery({ queryKey: ["user-roles", userId], queryFn: () => rbacApi.userRoles(userId), enabled: Boolean(userId) });
  const assign = useMutation({ mutationFn: (roleId: string) => rbacApi.assignRole(userId, roleId), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (roleId: string) => rbacApi.removeRole(userId, roleId), onSuccess: refresh });
  return { roles, assign, remove };
}

export function useUserOverrides(userId: string) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["user-overrides", userId], queryFn: () => rbacApi.overrides(userId), enabled: Boolean(userId) });
  const create = useMutation({ mutationFn: (input: { permission_id: string; company_id?: string; branch_id?: string; is_granted: boolean }) => rbacApi.createOverride(userId, input), onSuccess: () => client.invalidateQueries({ queryKey: ["user-overrides", userId] }) });
  const deactivate = useMutation({ mutationFn: (id: string) => rbacApi.deactivateOverride(id), onSuccess: () => client.invalidateQueries({ queryKey: ["user-overrides", userId] }) });
  return { query, create, deactivate };
}
