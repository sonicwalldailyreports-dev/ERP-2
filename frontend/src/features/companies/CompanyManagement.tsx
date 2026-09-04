import { useState } from "react";
import { Alert, Button, Card, CardContent, DialogActions, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { organizationApi } from "../../services/organizationApi";
import { DataTable } from "../../components/DataTable";
import { ReusableDialog } from "../../components/ReusableDialog";
import { useNotification } from "../../components/NotificationProvider";

export function CompanyManagement() {
  const queryClient = useQueryClient(); const { notify } = useNotification(); const [open, setOpen] = useState(false); const [name, setName] = useState(""); const [code, setCode] = useState("");
  const query = useQuery({ queryKey: ["companies"], queryFn: organizationApi.companies });
  const create = useMutation({ mutationFn: () => organizationApi.createCompany({ name, code }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["companies"] }); setOpen(false); setName(""); setCode(""); notify({ severity: "success", message: "Company created." }); } });
  return <><Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}><Typography variant="h4">Companies</Typography><Button variant="contained" onClick={() => setOpen(true)}>Add company</Button></Stack>{query.isError && <Alert severity="error">Unable to load companies.</Alert>}<Card><CardContent><DataTable columns={["Name", "Code", "Status"]} rows={(query.data ?? []).map((company) => [company.name, company.code, company.is_active ? "Active" : "Inactive"])} /></CardContent></Card><ReusableDialog open={open} title="Add company" onClose={() => setOpen(false)}><Stack spacing={2} sx={{ pt: 1 }}><TextField label="Company name" value={name} onChange={(event) => setName(event.target.value)} /><TextField label="Code" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /><DialogActions><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="contained" disabled={!name || !code || create.isPending} onClick={() => create.mutate()}>Create</Button></DialogActions></Stack></ReusableDialog></>;
}
