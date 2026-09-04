import { useState } from "react";
import { Alert, Button, Card, CardContent, DialogActions, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useOrganization } from "../../app/OrganizationContext";
import { organizationApi } from "../../services/organizationApi";
import { DataTable } from "../../components/DataTable";
import { ReusableDialog } from "../../components/ReusableDialog";
import { useNotification } from "../../components/NotificationProvider";

export function BranchManagement() {
  const { companyId } = useOrganization(); const queryClient = useQueryClient(); const { notify } = useNotification();
  const [open, setOpen] = useState(false); const [name, setName] = useState(""); const [code, setCode] = useState("");
  const query = useQuery({ queryKey: ["branches", companyId], queryFn: () => organizationApi.branches(companyId), enabled: Boolean(companyId) });
  const create = useMutation({ mutationFn: () => organizationApi.createBranch({ company_id: companyId, name, code }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["branches", companyId] }); setOpen(false); setName(""); setCode(""); notify({ severity: "success", message: "Branch created." }); } });
  return <><Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}><Typography variant="h4">Branches</Typography>{companyId && <Button variant="contained" onClick={() => setOpen(true)}>Add branch</Button>}</Stack>{!companyId ? <Alert severity="info">Select a company to manage its branches.</Alert> : <Card><CardContent><DataTable columns={["Name", "Code", "Status"]} rows={(query.data ?? []).map((branch) => [branch.name, branch.code, branch.is_active ? "Active" : "Inactive"])} /></CardContent></Card>}<ReusableDialog open={open} title="Add branch" onClose={() => setOpen(false)}><Stack spacing={2} sx={{ pt: 1 }}><TextField label="Branch name" value={name} onChange={(event) => setName(event.target.value)} /><TextField label="Code" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /><DialogActions><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="contained" disabled={!name || !code || create.isPending} onClick={() => create.mutate()}>Create</Button></DialogActions></Stack></ReusableDialog></>;
}
