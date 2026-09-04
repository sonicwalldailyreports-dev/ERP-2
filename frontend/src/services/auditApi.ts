import { apiClient } from "./apiClient";
import type { AuditLogResponse } from "../types/audit";

export type AuditFilters = {
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  module?: string;
  action?: string;
  entity?: string;
  entityId?: string;
  companyId?: string;
  branchId?: string;
  page?: number;
  pageSize?: number;
};

export const auditApi = {
  list: (filters: AuditFilters) => {
    const query = new URLSearchParams();
    const values: Record<string, string | undefined> = {
      date_from: filters.dateFrom, date_to: filters.dateTo, user_id: filters.userId,
      module: filters.module, action: filters.action, entity: filters.entity,
      entity_id: filters.entityId, company_id: filters.companyId, branch_id: filters.branchId,
    };
    Object.entries(values).forEach(([key, value]) => { if (value) query.set(key, value); });
    query.set("page", String(filters.page ?? 1));
    query.set("page_size", String(filters.pageSize ?? 25));
    return apiClient<AuditLogResponse>(`/audit/logs?${query.toString()}`);
  },
};
