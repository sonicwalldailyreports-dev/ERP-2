import { useState } from "react";
import {
  Alert, Button, Card, CardContent, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import { useOrganization } from "../../app/OrganizationContext";
import { DataTable } from "../../components/DataTable";
import { useNotification } from "../../components/NotificationProvider";
import type { Vendor } from "../../types/vendors";
import type { VendorInput } from "../../services/vendorsApi";
import { useVendorMutations, useVendors } from "./useVendors";

const emptyForm: VendorInput = {
  vendor_code: "", vendor_name: "", company_name: "", contact_person: "", email: "", phone: "",
  address: "", tax_number: "", opening_balance: "0.00", credit_limit: "", payment_terms: "",
  address_line1: "", address_line2: "", city: "", state: "", postal_code: "", country: "", tax_id: "", notes: "",
};

export function VendorManagement() {
  const { companyId, branchId } = useOrganization();
  const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false); const [details, setDetails] = useState<Vendor | null>(null);
  const [editing, setEditing] = useState<Vendor | null>(null); const [form, setForm] = useState<VendorInput>(emptyForm);
  const query = useVendors({ companyId: companyId || undefined, branchId: branchId || undefined, search, status, page });
  const mutations = useVendorMutations(companyId || undefined, branchId || undefined); const { notify } = useNotification();
  const update = (key: keyof VendorInput, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const closeForm = () => { setOpen(false); setEditing(null); setForm(emptyForm); };
  const editVendor = (vendor: Vendor) => {
    setEditing(vendor);
    setForm({ ...emptyForm, ...vendor, vendor_name: vendor.vendor_name, address: vendor.address_line1 ?? "" });
    setOpen(true);
  };
  const submit = async () => {
    if (editing) await mutations.update.mutateAsync({ id: editing.id, input: form });
    else await mutations.create.mutateAsync(form);
    closeForm(); notify({ severity: "success", message: editing ? "Vendor updated." : "Vendor created." });
  };
  return <Stack spacing={3}>
    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} gap={2}>
      <div><Typography variant="h4">Vendors</Typography><Typography color="text.secondary">Manage vendor master records for the selected organization.</Typography></div>
      <Button variant="contained" disabled={!companyId} onClick={() => setOpen(true)}>Add vendor</Button>
    </Stack>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
      <TextField size="small" label="Search vendors" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} fullWidth />
      <TextField select size="small" label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} sx={{ minWidth: 160 }}>
        <MenuItem value="">All</MenuItem><MenuItem value="active">Active</MenuItem><MenuItem value="inactive">Inactive</MenuItem><MenuItem value="suspended">Suspended</MenuItem>
      </TextField>
    </Stack>
    {!companyId && <Alert severity="info">Select a company to view vendors.</Alert>}
    {query.isError && <Alert severity="error">Unable to load vendors.</Alert>}
    <Card><CardContent><DataTable columns={["Code", "Name", "Contact", "Phone", "Status", "Actions"]} rows={(query.data?.items ?? []).map((vendor) => [
      vendor.vendor_code, vendor.vendor_name, vendor.contact_person ?? vendor.email ?? "—", vendor.phone ?? "—", vendor.status,
      <Stack direction={{ xs: "column", sm: "row" }} key={vendor.id}>
        <Button size="small" onClick={() => setDetails(vendor)}>Details</Button>
        <Button size="small" onClick={() => editVendor(vendor)}>Edit</Button>
        <Button size="small" onClick={() => mutations.setActive.mutate({ id: vendor.id, active: !vendor.is_active })}>{vendor.is_active ? "Deactivate" : "Activate"}</Button>
        <Button size="small" color="error" onClick={() => mutations.remove.mutate(vendor.id)}>Delete</Button>
      </Stack>,
    ])} /><Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}><Typography variant="body2">Showing {query.data?.items.length ?? 0} of {query.data?.total ?? 0}</Typography><Stack direction="row"><Button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}>Next</Button></Stack></Stack></CardContent></Card>
    <Dialog open={open} onClose={closeForm} fullWidth maxWidth="md"><DialogTitle>{editing ? "Edit vendor" : "Add vendor"}</DialogTitle><DialogContent><Stack spacing={2} sx={{ mt: 1 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Vendor code" value={form.vendor_code} onChange={(e) => update("vendor_code", e.target.value.toUpperCase())} required fullWidth /><TextField label="Vendor name" value={form.vendor_name ?? ""} onChange={(e) => update("vendor_name", e.target.value)} required fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Contact person" value={form.contact_person ?? ""} onChange={(e) => update("contact_person", e.target.value)} fullWidth /><TextField label="Email" value={form.email ?? ""} onChange={(e) => update("email", e.target.value)} fullWidth /><TextField label="Phone" value={form.phone ?? ""} onChange={(e) => update("phone", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Company name" value={form.company_name ?? ""} onChange={(e) => update("company_name", e.target.value)} fullWidth /><TextField label="Address" value={form.address ?? form.address_line1 ?? ""} onChange={(e) => update("address", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="City" value={form.city ?? ""} onChange={(e) => update("city", e.target.value)} fullWidth /><TextField label="State" value={form.state ?? ""} onChange={(e) => update("state", e.target.value)} fullWidth /><TextField label="Postal code" value={form.postal_code ?? ""} onChange={(e) => update("postal_code", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Country" value={form.country ?? ""} onChange={(e) => update("country", e.target.value)} fullWidth /><TextField label="Tax number" value={form.tax_number ?? ""} onChange={(e) => update("tax_number", e.target.value)} fullWidth /></Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Opening balance" type="number" value={form.opening_balance ?? "0.00"} onChange={(e) => update("opening_balance", e.target.value)} fullWidth /><TextField label="Credit limit" type="number" value={form.credit_limit ?? ""} onChange={(e) => update("credit_limit", e.target.value)} fullWidth /><TextField label="Payment terms" value={form.payment_terms ?? ""} onChange={(e) => update("payment_terms", e.target.value)} fullWidth /></Stack>
      <TextField label="Notes" value={form.notes ?? ""} onChange={(e) => update("notes", e.target.value)} multiline minRows={3} />
    </Stack></DialogContent><DialogActions><Button onClick={closeForm}>Cancel</Button><Button variant="contained" disabled={!form.vendor_code || !form.vendor_name || mutations.create.isPending || mutations.update.isPending} onClick={submit}>Save</Button></DialogActions></Dialog>
    <Dialog open={Boolean(details)} onClose={() => setDetails(null)} fullWidth maxWidth="sm"><DialogTitle>{details?.vendor_name}</DialogTitle><DialogContent><Stack spacing={1}><Typography><strong>Code:</strong> {details?.vendor_code}</Typography><Typography><strong>Email:</strong> {details?.email ?? "—"}</Typography><Typography><strong>Phone:</strong> {details?.phone ?? "—"}</Typography><Typography><strong>Address:</strong> {[details?.address_line1, details?.city, details?.state, details?.postal_code].filter(Boolean).join(", ") || "—"}</Typography><Typography variant="h6" sx={{ mt: 2 }}>Transaction history</Typography><Typography color="text.secondary">Transaction history will be available when the financial transactions module is enabled.</Typography></Stack></DialogContent><DialogActions><Button onClick={() => setDetails(null)}>Close</Button></DialogActions></Dialog>
  </Stack>;
}
