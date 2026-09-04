export type ExpenseStatus = "DRAFT" | "SUBMITTED" | "APPROVED" | "POSTED" | "REJECTED" | "CANCELLED";

export type ExpenseCategory = {
  id: string; company_id: string; branch_id: string | null; code: string; name: string;
  description: string | null; is_active: boolean; created_at: string; updated_at: string;
};

export type Expense = {
  id: string; company_id: string; branch_id: string | null; financial_year_id: string;
  expense_number: string; date: string; category_id: string; account_id: string;
  description: string | null; vendor: string | null; amount: string; tax_amount: string;
  payment_method: string; cash_account_id: string | null; reference: string | null;
  attachment: Record<string, unknown> | unknown[] | null; status: ExpenseStatus;
  created_by: string | null; approved_by: string | null; posted_by: string | null;
  approved_at: string | null; posted_at: string | null; rejection_reason: string | null;
  cancellation_reason: string | null; reversal_of_id: string | null; correction_of_id: string | null;
  created_at: string; updated_at: string;
};
