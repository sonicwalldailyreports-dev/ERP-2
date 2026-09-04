import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { vendorsApi, type VendorInput } from "../../services/vendorsApi";

export function useVendors(params: { companyId?: string; branchId?: string; search?: string; status?: string; page?: number }) {
  return useQuery({
    queryKey: ["vendors", params],
    queryFn: () => vendorsApi.list({ companyId: params.companyId!, branchId: params.branchId, search: params.search, status: params.status, page: params.page }),
    enabled: Boolean(params.companyId),
  });
}

export function useVendor(id?: string) {
  return useQuery({
    queryKey: ["vendor", id],
    queryFn: () => vendorsApi.get(id!),
    enabled: Boolean(id),
  });
}

export function useVendorMutations(companyId?: string, branchId?: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["vendors"] });
  return {
    create: useMutation({ mutationFn: (input: VendorInput) => vendorsApi.create(companyId!, branchId, input), onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, input }: { id: string; input: Partial<VendorInput> }) => vendorsApi.update(id, input), onSuccess: refresh }),
    setActive: useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => vendorsApi.setActive(id, active), onSuccess: refresh }),
    remove: useMutation({ mutationFn: (id: string) => vendorsApi.remove(id), onSuccess: refresh }),
  };
}
