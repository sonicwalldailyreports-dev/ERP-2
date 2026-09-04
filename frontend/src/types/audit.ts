export type AuditLog = {
  id: string;
  user_id: string | null;
  company_id: string | null;
  branch_id: string | null;
  action: string;
  module: string;
  entity_type: string;
  entity_id: string | null;
  timestamp: string;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  details: string | null;
};

export type AuditLogResponse = {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
