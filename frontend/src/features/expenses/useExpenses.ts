import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expensesApi, type ExpenseInput } from "../../services/expensesApi";

export function useExpenses(companyId?: string, branchId?: string, status?: string, search?: string) {
  const client = useQueryClient();
  const key = ["expenses", companyId, branchId];
  const categories = useQuery({ queryKey: [...key, "categories"], queryFn: () => expensesApi.categories(companyId!, branchId), enabled: Boolean(companyId) });
  const expenses = useQuery({ queryKey: [...key, "list", status, search], queryFn: () => expensesApi.list({ companyId: companyId!, branchId, status, search }), enabled: Boolean(companyId) });
  const refresh = () => client.invalidateQueries({ queryKey: ["expenses"] });
  const create = useMutation({ mutationFn: (input: ExpenseInput) => expensesApi.create(input), onSuccess: refresh });
  const transition = useMutation({ mutationFn: ({ id, action }: { id: string; action: "submit" | "approve" | "post" | "reverse" | "adjust" }) => expensesApi.transition(id, action), onSuccess: refresh });
  const reject = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => expensesApi.reject(id, reason), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => expensesApi.cancel(id, reason), onSuccess: refresh });
  const createCategory = useMutation({ mutationFn: expensesApi.createCategory, onSuccess: refresh });
  return { categories, expenses, create, transition, reject, cancel, createCategory };
}
