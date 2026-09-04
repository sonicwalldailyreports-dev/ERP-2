export type CashAccount = {
  id: string; company_id: string; branch_id: string | null; account_id: string | null;
  account_code: string; name: string; currency: string; opening_balance: string;
  balance: string; is_active: boolean; deleted_at: string | null; created_at: string; updated_at: string;
};

export type CashTransaction = {
  id: string; company_id: string; branch_id: string | null; cash_account_id: string;
  target_cash_account_id: string | null; financial_year_id: string; transaction_type: "receipt" | "payment" | "transfer";
  transaction_date: string; amount: string; reference: string | null; description: string | null;
  document_number: string | null; state: "DRAFT" | "SUBMITTED" | "APPROVED" | "POSTED" | "REJECTED" | "CANCELLED";
  rejection_reason: string | null; cancellation_reason: string | null; reversal_of_id: string | null;
  created_by: string | null; submitted_by: string | null; approved_by: string | null; posted_by: string | null;
  reversed_by: string | null; submitted_at: string | null; approved_at: string | null; posted_at: string | null;
  cancelled_at: string | null; reversed_at: string | null; created_at: string; updated_at: string;
};

export type DailySummary = {
  summary_date: string; cash_account_id: string; cash_account_name: string; opening_balance: string;
  receipts: string; payments: string; transfers_in: string; transfers_out: string; closing_balance: string;
};
