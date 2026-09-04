import { apiClient } from "./apiClient";
import type { Expense, ExpenseCategory } from "../types/expenses";

export type ExpenseInput = {
  company_id: string; branch_id?: string | null; financial_year_id: string; date: string;
  category_id: string; account_id: string; description?: string; vendor?: string;
  amount: string; tax_amount: string; payment_method: string; cash_account_id?: string | null;
  reference?: string; attachment?: Record<string, unknown> | unknown[] | null;
};

export const expensesApi = {
  categories: (companyId: string, branchId?: string) => apiClient<ExpenseCategory[]>(
    `/expenses/categories?company_id=${companyId}${branchId ? `&branch_id=${branchId}` : ""}`,
  ),
  createCategory: (input: { company_id: string; branch_id?: string | null; code: string; name: string; description?: string }) =>
    apiClient<ExpenseCategory>("/expenses/categories", { method: "POST", body: JSON.stringify(input) }),
  list: (params: { companyId: string; branchId?: string; status?: string; categoryId?: string; search?: string }) => {
    const query = new URLSearchParams({ company_id: params.companyId });
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.status) query.set("status", params.status);
    if (params.categoryId) query.set("category_id", params.categoryId);
    if (params.search) query.set("search", params.search);
    return apiClient<Expense[]>(`/expenses?${query}`);
  },
  create: (input: ExpenseInput) => apiClient<Expense>("/expenses", { method: "POST", body: JSON.stringify(input) }),
  update: (id: string, input: Partial<ExpenseInput>) => apiClient<Expense>(`/expenses/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  transition: (id: string, action: "submit" | "approve" | "post" | "reverse" | "adjust", body?: object) =>
    apiClient<Expense>(`/expenses/${id}/${action}`, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  reject: (id: string, reason: string) => apiClient<Expense>(`/expenses/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  cancel: (id: string, reason: string) => apiClient<Expense>(`/expenses/${id}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }),
};
