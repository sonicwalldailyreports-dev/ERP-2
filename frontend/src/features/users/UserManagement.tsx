import { useState } from "react";
import {
  Alert, Button, Card, CardContent, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import { useOrganization } from "../../app/OrganizationContext";
import { DataTable } from "../../components/DataTable";
import { useNotification } from "../../components/NotificationProvider";
import { useRoles } from "../roles/useRoles";
import { useUserMutations, useUserPermissions, useUsers } from "./useUsers";
import type { ManagedUser } from "../../types/users";

export function UserManagement() {
  const { companyId, branchId, companies, branches } = useOrganization();
  const [search, setSearch] = useState(""); const [status, setStatus] = useState("");
  const [page, setPage] = useState(1); const [open, setOpen] = useState(false); const [selected, setSelected] = useState<string>(""); const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [form, setForm] = useState({ username: "", email: "", full_name: "", phone: "", password: "", role_ids: [] as string[] });
  const query = useUsers({ companyId: companyId || undefined, branchId: branchId || undefined, search, status: status || undefined, page });
  const roles = useRoles(companyId || undefined); const mutations = useUserMutations(); const { notify } = useNotification();
  const permissions = useUserPermissions(selected, Boolean(selected));
  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    if (editing) {
      await mutations.update.mutateAsync({ id: editing.id, username: form.username, email: form.email, full_name: form.full_name, phone: form.phone, role_ids: form.role_ids, company_ids: editing.company_ids, branch_assignments: editing.branch_assignments });
      notify({ severity: "success", message: "User updated." });
    } else {
      await mutations.create.mutateAsync({ ...form, company_ids: companyId ? [companyId] : [], branch_assignments: branches.length && companyId ? [{ company_id: companyId, branch_id: branches[0].id }] : [] });
      notify({ severity: "success", message: "User created." });
    }
    setOpen(false); setEditing(null); setForm({ username: "", email: "", full_name: "", phone: "", password: "", role_ids: [] });
  };
  return <Stack spacing={3}>
    <Stack direction="row" justifyContent="space-between" alignItems="center"><div><Typography variant="h4">Users</Typography><Typography color="text.secondary">Manage accounts, assignments and access.</Typography></div><Button variant="contained" disabled={!companyId} onClick={() => setOpen(true)}>Add user</Button></Stack>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField size="small" label="Search users" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /><TextField select size="small" label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} sx={{ minWidth: 150 }}><MenuItem value="">All</MenuItem><MenuItem value="active">Active</MenuItem><MenuItem value="inactive">Inactive</MenuItem><MenuItem value="suspended">Suspended</MenuItem></TextField></Stack>
    {query.isError && <Alert severity="error">Unable to load users.</Alert>}
    <Card><CardContent><DataTable columns={["Name", "Username", "Email", "Role assignments", "Status", "Actions"]} rows={(query.data?.items ?? []).map((user) => [
      user.full_name, user.username ?? "—", user.email, String(user.role_ids.length), user.status,
      <Stack direction="row" key={user.id}><Button size="small" onClick={() => { setSelected(user.id); }}>Permissions</Button><Button size="small" onClick={() => { setEditing(user); setForm({ username: user.username ?? "", email: user.email, full_name: user.full_name, phone: user.phone ?? "", password: "", role_ids: user.role_ids }); setOpen(true); }}>Edit</Button><Button size="small" onClick={() => mutations.setActive.mutate({ id: user.id, active: !user.is_active })}>{user.is_active ? "Deactivate" : "Activate"}</Button><Button size="small" onClick={() => mutations.resetPassword.mutate({ id: user.id })}>Reset password</Button></Stack>,
    ])} /><Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}><Typography variant="body2">Showing {query.data?.items.length ?? 0} of {query.data?.total ?? 0}</Typography><Stack direction="row"><Button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}>Next</Button></Stack></Stack></CardContent></Card>
    <Dialog open={Boolean(selected)} onClose={() => setSelected("")} fullWidth maxWidth="sm"><DialogTitle>Permission summary</DialogTitle><DialogContent><Typography sx={{ mb: 2 }}>{permissions.data?.permissions.length ?? 0} effective permissions</Typography>{permissions.data?.permissions.map((permission) => <Typography key={permission} variant="body2">{permission}</Typography>)}</DialogContent><DialogActions><Button onClick={() => setSelected("")}>Close</Button></DialogActions></Dialog>
    <Dialog open={open} onClose={() => { setOpen(false); setEditing(null); }} fullWidth maxWidth="sm"><DialogTitle>{editing ? "Edit user" : "Add user"}</DialogTitle><DialogContent><Stack spacing={2} sx={{ mt: 1 }}><TextField label="Full name" value={form.full_name} onChange={(e) => update("full_name", e.target.value)} required /><TextField label="Username" value={form.username} onChange={(e) => update("username", e.target.value)} required /><TextField label="Email" value={form.email} onChange={(e) => update("email", e.target.value)} required /><TextField label="Phone" value={form.phone} onChange={(e) => update("phone", e.target.value)} />{!editing && <TextField label="Temporary password" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} required />}<TextField select label="Role" value={form.role_ids[0] ?? ""} onChange={(e) => setForm((current) => ({ ...current, role_ids: e.target.value ? [e.target.value] : [] }))}>{roles.data?.map((role) => <MenuItem key={role.id} value={role.id}>{role.name}</MenuItem>)}</TextField><FormControlLabel control={<Checkbox checked={Boolean(companyId)} disabled />} label={`Company: ${companies.find((item) => item.id === companyId)?.name ?? "Select a company"}`} /></Stack></DialogContent><DialogActions><Button onClick={() => { setOpen(false); setEditing(null); }}>Cancel</Button><Button variant="contained" disabled={!form.full_name || !form.username || !form.email || (!editing && form.password.length < 12) || mutations.create.isPending || mutations.update.isPending} onClick={submit}>{editing ? "Save" : "Create"}</Button></DialogActions></Dialog>
  </Stack>;
}
