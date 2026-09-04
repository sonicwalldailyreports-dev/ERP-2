import { Alert, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { useNavigate, useParams } from "react-router-dom";
import { useVendor } from "./useVendors";

export function VendorDetails() {
  const { vendorId } = useParams();
  const navigate = useNavigate();
  const query = useVendor(vendorId);
  if (query.isLoading) return <Typography>Loading vendor…</Typography>;
  if (query.isError || !query.data) return <Alert severity="error">Unable to load vendor.</Alert>;
  const vendor = query.data;
  return <Stack spacing={3}>
    <Stack direction="row" justifyContent="space-between" alignItems="center">
      <div><Typography variant="h4">{vendor.vendor_name}</Typography><Typography color="text.secondary">{vendor.vendor_code}</Typography></div>
      <Button onClick={() => navigate("/vendors")}>Back to vendors</Button>
    </Stack>
    <Card><CardContent><Stack spacing={1}>
      <Typography><strong>Contact:</strong> {vendor.contact_person ?? "—"}</Typography>
      <Typography><strong>Email:</strong> {vendor.email ?? "—"}</Typography>
      <Typography><strong>Phone:</strong> {vendor.phone ?? "—"}</Typography>
      <Typography><strong>Address:</strong> {[vendor.address_line1, vendor.city, vendor.state, vendor.postal_code].filter(Boolean).join(", ") || "—"}</Typography>
      <Typography><strong>Tax number:</strong> {vendor.tax_number ?? vendor.tax_id ?? "—"}</Typography>
      <Typography><strong>Status:</strong> {vendor.status}</Typography>
    </Stack></CardContent></Card>
    <Card><CardContent><Typography variant="h6">Transaction history</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>Transaction history will be available when the financial transactions module is enabled.</Typography></CardContent></Card>
  </Stack>;
}
