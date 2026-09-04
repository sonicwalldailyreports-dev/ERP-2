import { apiClient } from "./apiClient";
import type { DashboardData } from "../types/dashboard";

export const dashboardApi = {
  summary: (params: { companyId: string; branchId?: string; startDate?: string; endDate?: string; page?: number; pageSize?: number }) => {
    const query = new URLSearchParams({ company_id: params.companyId });
    if (params.branchId) query.set("branch_id", params.branchId);
    if (params.startDate) query.set("start_date", params.startDate);
    if (params.endDate) query.set("end_date", params.endDate);
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.pageSize ?? 8));
    return apiClient<DashboardData>(`/dashboard?${query.toString()}`);
  },
};
