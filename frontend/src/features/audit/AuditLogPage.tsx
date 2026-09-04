import { useState } from "react";
import {
  Alert, Button, Card, CardContent, Collapse, MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "../../app/OrganizationContext";
import { DataTable } from "../../components/DataTable";
import { auditApi, type AuditFilters } from "../../services/auditApi";

function formatJson(value: unknown) {
  return value ? JSON.stringify(value, null, 2) : "—";
}

export function AuditLogPage() {
  const { companyId, branchId, companies, branches } = useOrganization();
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string>("");
  const [filters, setFilters] = useState<AuditFilters>({ companyId: companyId || undefined, branchId: branchId || undefined });
  const selectedCompany = filters.companyId === undefined ? companyId || undefined : filters.companyId;
  const selectedBranch = filters.branchId === undefined ? branchId || undefined : filters.branchId;
  const update = (key: keyof AuditFilters, value: string) => {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  };
  const query = useQuery({
    queryKey: ["audit-logs", filters, selectedCompany, selectedBranch, page],
    queryFn: () => auditApi.list({ ...filters, companyId: selectedCompany, branchId: selectedBranch, page }),
  });
  return <Stack spacing={3}>
    <div><Typography variant="h4">Audit logs</Typography><Typography color="text.secondary">Immutable activity history for authorized administrators.</Typography></div>
    <Card><CardContent><Stack direction={{ xs: "column", md: "row" }} spacing={2} flexWrap="wrap">
      <TextField size="small" type="datetime-local" label="From" InputLabelProps={{ shrink: true }} onChange={(e) => update("dateFrom", e.target.value ? new Date(e.target.value).toISOString() : "")} />
      <TextField size="small" type="datetime-local" label="To" InputLabelProps={{ shrink: true }} onChange={(e) => update("dateTo", e.target.value ? new Date(e.target.value).toISOString() : "")} />
      <TextField size="small" label="User ID" onChange={(e) => update("userId", e.target.value)} />
      <TextField select size="small" label="Company" value={selectedCompany ?? ""} onChange={(e) => { setPage(1); setFilters((current) => ({ ...current, companyId: e.target.value || "", branchId: undefined })); }} sx={{ minWidth: 180 }}>
        <MenuItem value="">All assigned companies</MenuItem>{companies.map((company) => <MenuItem key={company.id} value={company.id}>{company.name}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Branch" value={selectedBranch ?? ""} onChange={(e) => { setPage(1); setFilters((current) => ({ ...current, branchId: e.target.value || "" })); }} sx={{ minWidth: 160 }}>
        <MenuItem value="">All branches</MenuItem>{branches.map((branch) => <MenuItem key={branch.id} value={branch.id}>{branch.name}</MenuItem>)}
      </TextField>
      <TextField size="small" label="Module" onChange={(e) => update("module", e.target.value)} />
      <TextField size="small" label="Action" onChange={(e) => update("action", e.target.value)} />
      <TextField size="small" label="Entity" onChange={(e) => update("entity", e.target.value)} />
    </Stack></CardContent></Card>
    {query.isError && <Alert severity="error">Unable to load audit logs. You may not have permission.</Alert>}
    <Card><CardContent><DataTable columns={["Time", "Action", "Module", "Entity", "User", "Request", "Details"]} rows={(query.data?.items ?? []).map((item) => [
      new Date(item.timestamp).toLocaleString(), item.action, item.module, `${item.entity_type}${item.entity_id ? ` (${item.entity_id.slice(0, 8)})` : ""}`,
      item.user_id?.slice(0, 8) ?? "System", item.request_id?.slice(0, 12) ?? "—",
      <div key={item.id}><Button size="small" onClick={() => setExpanded(expanded === item.id ? "" : item.id)}>View</Button><Collapse in={expanded === item.id}><Typography component="pre" variant="caption" sx={{ whiteSpace: "pre-wrap" }}>Before: {formatJson(item.before_data)}{"\n"}After: {formatJson(item.after_data)}</Typography></Collapse></div>,
    ])} /><Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}><Typography variant="body2">Showing {query.data?.items.length ?? 0} of {query.data?.total ?? 0}</Typography><Stack direction="row"><Button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}>Next</Button></Stack></Stack></CardContent></Card>
  </Stack>;
}
