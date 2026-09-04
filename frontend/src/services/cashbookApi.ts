import { apiClient } from "./apiClient";
import type { CashAccount, CashTransaction, DailySummary } from "../types/cashbook";

export type CashTransactionInput = {
  company_id: string; branch_id?: string | null; cash_account_id: string; target_cash_account_id?: string | null;
  financial_year_id: string; transaction_type: "receipt" | "payment" | "transfer"; transaction_date: string;
  amount: string; reference?: string; description?: string;
};

export const cashbookApi = {
  accounts: (companyId: string, branchId?: string) => apiClient<CashAccount[]>(`/cash-book/accounts?company_id=${companyId}${branchId ? `&branch_id=${branchId}` : ""}`),
  createAccount: (input: { company_id: string; branch_id?: string | null; account_code: string; name: string; currency: string; opening_balance: string }) =>
    apiClient<CashAccount>("/cash-book/accounts", { method: "POST", body: JSON.stringify(input) }),
  transactions: (params: { companyId: string; branchId?: string; state?: string }) => {
    const query = new URLSearchParams({ company_id: params.companyId });
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.state) query.set("state", params.state);
    return apiClient<CashTransaction[]>(`/cash-book/transactions?${query}`);
  },
  create: (input: CashTransactionInput) => apiClient<CashTransaction>("/cash-book/transactions", { method: "POST", body: JSON.stringify(input) }),
  transition: (id: string, action: "submit" | "approve" | "post" | "reverse", body?: object) =>
    apiClient<CashTransaction>(`/cash-book/transactions/${id}/${action}`, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  reject: (id: string, reason: string) => apiClient<CashTransaction>(`/cash-book/transactions/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  cancel: (id: string, reason: string) => apiClient<CashTransaction>(`/cash-book/transactions/${id}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }),
  summary: (companyId: string, branchId?: string, summaryDate?: string) => {
    const query = new URLSearchParams({ company_id: companyId });
    if (branchId) query.set("branch_id", branchId);
    if (summaryDate) query.set("summary_date", summaryDate);
    return apiClient<DailySummary[]>(`/cash-book/daily-summary?${query}`);
  },
};
