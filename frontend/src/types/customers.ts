export type Customer = {
  id: string;
  company_id: string;
  branch_id: string | null;
  customer_code: string;
  name: string;
  customer_name: string;
  company_name: string | null;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  tax_id: string | null;
  tax_number: string | null;
  opening_balance: string;
  credit_limit: string | null;
  payment_terms: string | null;
  notes: string | null;
  status: "active" | "inactive" | "suspended";
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerListResponse = {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
