import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cashbookApi, type CashTransactionInput } from "../../services/cashbookApi";

export function useCashBook(companyId?: string, branchId?: string) {
  const client = useQueryClient();
  const key = ["cashbook", companyId, branchId];
  const accounts = useQuery({ queryKey: [...key, "accounts"], queryFn: () => cashbookApi.accounts(companyId!, branchId), enabled: Boolean(companyId) });
  const transactions = useQuery({ queryKey: [...key, "transactions"], queryFn: () => cashbookApi.transactions({ companyId: companyId!, branchId }), enabled: Boolean(companyId) });
  const summary = useQuery({ queryKey: [...key, "summary"], queryFn: () => cashbookApi.summary(companyId!, branchId), enabled: Boolean(companyId) });
  const refresh = () => client.invalidateQueries({ queryKey: ["cashbook"] });
  const create = useMutation({ mutationFn: (input: CashTransactionInput) => cashbookApi.create(input), onSuccess: refresh });
  const transition = useMutation({ mutationFn: ({ id, action }: { id: string; action: "submit" | "approve" | "post" | "reverse" }) => cashbookApi.transition(id, action), onSuccess: refresh });
  const reject = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => cashbookApi.reject(id, reason), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => cashbookApi.cancel(id, reason), onSuccess: refresh });
  const createAccount = useMutation({ mutationFn: cashbookApi.createAccount, onSuccess: refresh });
  return { accounts, transactions, summary, create, transition, reject, cancel, createAccount };
}
