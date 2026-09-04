export type Permission = {
  id: string;
  code: string;
  description: string | null;
  is_active: boolean;
};

export type Role = {
  id: string;
  company_id: string | null;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
};

export type UserPermissionOverride = {
  id: string;
  user_id: string;
  permission_id: string;
  company_id: string | null;
  branch_id: string | null;
  is_granted: boolean;
  is_active: boolean;
};
