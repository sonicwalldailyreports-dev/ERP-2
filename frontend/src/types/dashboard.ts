export type DashboardCards = {
  income: string;
  expenses: string;
  cash_balance: string;
  bank_balance: string;
  receivables: string;
  payables: string;
};

export type DashboardPoint = {
  period: string;
  income: string;
  expenses: string;
  receipts: string;
  payments: string;
  net: string;
};

export type DashboardData = {
  company_id: string;
  branch_id: string | null;
  financial_year_id: string;
  start_date: string;
  end_date: string;
  cards: DashboardCards;
  income_vs_expense: DashboardPoint[];
  cash_flow: DashboardPoint[];
  expenses_by_category: { category_id: string; category: string; amount: string }[];
  branch_comparison: { branch_id: string | null; branch: string; income: string; expenses: string; net: string }[];
  recent_transactions: { id: string; transaction_number: string; transaction_date: string; description: string | null; reference: string | null; status: string; amount: string }[];
  pending_approvals: { id: string; kind: string; number: string; date: string; amount: string; status: string; description: string | null }[];
  recent_expenses: { id: string; expense_number: string; date: string; category: string; vendor: string | null; amount: string; status: string; description: string | null }[];
  customer_outstanding: { id: string; code: string; name: string; outstanding: string; branch_id: string | null }[];
  vendor_outstanding: { id: string; code: string; name: string; outstanding: string; branch_id: string | null }[];
  pagination: { page: number; page_size: number; total: number };
};
