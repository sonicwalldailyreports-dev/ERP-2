import { Alert, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { useNavigate, useParams } from "react-router-dom";
import { useCustomer } from "./useCustomers";

export function CustomerDetails() {
  const { customerId } = useParams(); const navigate = useNavigate(); const query = useCustomer(customerId);
  if (query.isLoading) return <Typography>Loading customer…</Typography>;
  if (query.isError || !query.data) return <Alert severity="error">Unable to load customer.</Alert>;
  const customer = query.data;
  return <Stack spacing={3}><Stack direction="row" justifyContent="space-between" alignItems="center"><div><Typography variant="h4">{customer.name}</Typography><Typography color="text.secondary">{customer.customer_code}</Typography></div><Button onClick={() => navigate("/customers")}>Back to customers</Button></Stack>
    <Card><CardContent><Stack spacing={1}><Typography><strong>Contact:</strong> {customer.contact_person ?? "—"}</Typography><Typography><strong>Email:</strong> {customer.email ?? "—"}</Typography><Typography><strong>Phone:</strong> {customer.phone ?? "—"}</Typography><Typography><strong>Address:</strong> {[customer.address_line1, customer.city, customer.state, customer.postal_code].filter(Boolean).join(", ") || "—"}</Typography><Typography><strong>Status:</strong> {customer.status}</Typography></Stack></CardContent></Card>
    <Card><CardContent><Typography variant="h6">Transaction history</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>Transaction history will be available when the financial transactions module is enabled.</Typography></CardContent></Card>
  </Stack>;
}
