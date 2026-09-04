import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "../../services/usersApi";

export function useUsers(params: { companyId?: string; branchId?: string; search?: string; status?: string; page?: number; pageSize?: number }) {
  return useQuery({ queryKey: ["users", params], queryFn: () => usersApi.list(params) });
}

export function useUserMutations() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["users"] });
  return {
    create: useMutation({ mutationFn: usersApi.create, onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, ...input }: { id: string; [key: string]: unknown }) => usersApi.update(id, input), onSuccess: refresh }),
    setActive: useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => usersApi.setActive(id, active), onSuccess: refresh }),
    resetPassword: useMutation({ mutationFn: ({ id, password }: { id: string; password?: string }) => usersApi.resetPassword(id, password) }),
  };
}

export function useUserPermissions(userId: string, enabled = true) {
  return useQuery({ queryKey: ["user-permissions", userId], queryFn: () => usersApi.permissions(userId), enabled: Boolean(userId) && enabled });
}
