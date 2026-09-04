import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { customersApi, type CustomerInput } from "../../services/customersApi";

export function useCustomers(params: { companyId?: string; branchId?: string; search?: string; status?: string; page?: number }) {
  return useQuery({
    queryKey: ["customers", params],
    queryFn: () => customersApi.list({ companyId: params.companyId!, branchId: params.branchId, search: params.search, status: params.status, page: params.page }),
    enabled: Boolean(params.companyId),
  });
}

export function useCustomer(id?: string) {
  return useQuery({
    queryKey: ["customer", id],
    queryFn: () => customersApi.get(id!),
    enabled: Boolean(id),
  });
}

export function useCustomerMutations(companyId?: string, branchId?: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["customers"] });
  return {
    create: useMutation({ mutationFn: (input: CustomerInput) => customersApi.create(companyId!, branchId, input), onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, input }: { id: string; input: Partial<CustomerInput> }) => customersApi.update(id, input), onSuccess: refresh }),
    setActive: useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => customersApi.setActive(id, active), onSuccess: refresh }),
    remove: useMutation({ mutationFn: (id: string) => customersApi.remove(id), onSuccess: refresh }),
  };
}
