export type BranchAssignment = { company_id: string; branch_id: string };

export type ManagedUser = {
  id: string;
  username: string | null;
  email: string;
  phone: string | null;
  full_name: string;
  status: "active" | "inactive" | "suspended";
  is_active: boolean;
  password_status: string;
  last_login_at: string | null;
  company_ids: string[];
  branch_assignments: BranchAssignment[];
  role_ids: string[];
  created_at: string;
  updated_at: string;
};

export type UserListResponse = { items: ManagedUser[]; total: number; page: number; page_size: number; pages: number };
export type PermissionSummary = { permissions: string[]; by_company: Record<string, string[]> };
