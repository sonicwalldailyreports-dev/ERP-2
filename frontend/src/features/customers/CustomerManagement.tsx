import { useState } from "react";
import {
  Alert, Button, Card, CardContent, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import { useOrganization } from "../../app/OrganizationContext";
import { DataTable } from "../../components/DataTable";
import { useNotification } from "../../components/NotificationProvider";
import type { Customer } from "../../types/customers";
import type { CustomerInput } from "../../services/customersApi";
import { useCustomerMutations, useCustomers } from "./useCustomers";

const emptyForm: CustomerInput = {
  customer_code: "", customer_name: "", company_name: "", contact_person: "", email: "", phone: "",
  address: "", tax_number: "", opening_balance: "0.00", credit_limit: "", payment_terms: "",
  address_line1: "", address_line2: "", city: "", state: "", postal_code: "", country: "", tax_id: "", notes: "",
};

export function CustomerManagement() {
  const { companyId, branchId } = useOrganization();
  const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false); const [details, setDetails] = useState<Customer | null>(null);
  const [editing, setEditing] = useState<Customer | null>(null); const [form, setForm] = useState<CustomerInput>(emptyForm);
  const query = useCustomers({ companyId: companyId || undefined, branchId: branchId || undefined, search, status, page });
  const mutations = useCustomerMutations(companyId || undefined, branchId || undefined); const { notify } = useNotification();
  const update = (key: keyof CustomerInput, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const closeForm = () => { setOpen(false); setEditing(null); setForm(emptyForm); };
  const submit = async () => {
    if (editing) await mutations.update.mutateAsync({ id: editing.id, input: form });
    else await mutations.create.mutateAsync(form);
    closeForm(); notify({ severity: "success", message: editing ? "Customer updated." : "Customer created." });
  };
  return <Stack spacing={3}>
    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} gap={2}>
      <div><Typography variant="h4">Customers</Typography><Typography color="text.secondary">Manage customer master records for the selected organization.</Typography></div>
      <Button variant="contained" disabled={!companyId} onClick={() => setOpen(true)}>Add customer</Button>
    </Stack>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
      <TextField size="small" label="Search customers" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} fullWidth />
      <TextField select size="small" label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} sx={{ minWidth: 160 }}>
        <MenuItem value="">All</MenuItem><MenuItem value="active">Active</MenuItem><MenuItem value="inactive">Inactive</MenuItem><MenuItem value="suspended">Suspended</MenuItem>
      </TextField>
    </Stack>
    {!companyId && <Alert severity="info">Select a company to view customers.</Alert>}
    {query.isError && <Alert severity="error">Unable to load customers.</Alert>}
    <Card><CardContent><DataTable columns={["Code", "Name", "Contact", "Phone", "Status", "Actions"]} rows={(query.data?.items ?? []).map((customer) => [
      customer.customer_code, customer.customer_name, customer.contact_person ?? customer.email ?? "—", customer.phone ?? "—", customer.status,
      <Stack direction={{ xs: "column", sm: "row" }} key={customer.id}><Button size="small" onClick={() => setDetails(customer)}>Details</Button><Button size="small" onClick={() => { setEditing(customer); setForm({ ...emptyForm, ...customer }); setOpen(true); }}>Edit</Button><Button size="small" onClick={() => mutations.setActive.mutate({ id: customer.id, active: !customer.is_active })}>{customer.is_active ? "Deactivate" : "Activate"}</Button></Stack>,
    ])} /><Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}><Typography variant="body2">Showing {query.data?.items.length ?? 0} of {query.data?.total ?? 0}</Typography><Stack direction="row"><Button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}>Next</Button></Stack></Stack></CardContent></Card>
    <Dialog open={open} onClose={closeForm} fullWidth maxWidth="md"><DialogTitle>{editing ? "Edit customer" : "Add customer"}</DialogTitle><DialogContent><Stack spacing={2} sx={{ mt: 1 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Customer code" value={form.customer_code} onChange={(e) => update("customer_code", e.target.value.toUpperCase())} required fullWidth /><TextField label="Customer name" value={form.customer_name ?? ""} onChange={(e) => update("customer_name", e.target.value)} required fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Contact person" value={form.contact_person ?? ""} onChange={(e) => update("contact_person", e.target.value)} fullWidth /><TextField label="Email" value={form.email ?? ""} onChange={(e) => update("email", e.target.value)} fullWidth /><TextField label="Phone" value={form.phone ?? ""} onChange={(e) => update("phone", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Company name" value={form.company_name ?? ""} onChange={(e) => update("company_name", e.target.value)} fullWidth /><TextField label="Address" value={form.address ?? form.address_line1 ?? ""} onChange={(e) => update("address", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="City" value={form.city ?? ""} onChange={(e) => update("city", e.target.value)} fullWidth /><TextField label="State" value={form.state ?? ""} onChange={(e) => update("state", e.target.value)} fullWidth /><TextField label="Postal code" value={form.postal_code ?? ""} onChange={(e) => update("postal_code", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Country" value={form.country ?? ""} onChange={(e) => update("country", e.target.value)} fullWidth /><TextField label="Tax number" value={form.tax_number ?? ""} onChange={(e) => update("tax_number", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Opening balance" type="number" value={form.opening_balance ?? "0.00"} onChange={(e) => update("opening_balance", e.target.value)} fullWidth /><TextField label="Credit limit" type="number" value={form.credit_limit ?? ""} onChange={(e) => update("credit_limit", e.target.value)} fullWidth /><TextField label="Payment terms" value={form.payment_terms ?? ""} onChange={(e) => update("payment_terms", e.target.value)} fullWidth /></Stack>
      <TextField label="Notes" value={form.notes ?? ""} onChange={(e) => update("notes", e.target.value)} multiline minRows={3} />
    </Stack></DialogContent><DialogActions><Button onClick={closeForm}>Cancel</Button><Button variant="contained" disabled={!form.customer_code || !form.customer_name || mutations.create.isPending || mutations.update.isPending} onClick={submit}>Save</Button></DialogActions></Dialog>
    <Dialog open={Boolean(details)} onClose={() => setDetails(null)} fullWidth maxWidth="sm"><DialogTitle>{details?.name}</DialogTitle><DialogContent><Stack spacing={1}><Typography><strong>Code:</strong> {details?.customer_code}</Typography><Typography><strong>Email:</strong> {details?.email ?? "—"}</Typography><Typography><strong>Phone:</strong> {details?.phone ?? "—"}</Typography><Typography><strong>Address:</strong> {[details?.address_line1, details?.city, details?.state, details?.postal_code].filter(Boolean).join(", ") || "—"}</Typography><Typography variant="h6" sx={{ mt: 2 }}>Transaction history</Typography><Typography color="text.secondary">Transaction history will be available when the financial transactions module is enabled.</Typography></Stack></DialogContent><DialogActions><Button onClick={() => setDetails(null)}>Close</Button></DialogActions></Dialog>
  </Stack>;
}
