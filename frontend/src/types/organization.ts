export type Company = { id: string; name: string; code: string; is_active: boolean; deleted_at: string | null };
export type Branch = { id: string; company_id: string; name: string; code: string; is_active: boolean; deleted_at: string | null };
