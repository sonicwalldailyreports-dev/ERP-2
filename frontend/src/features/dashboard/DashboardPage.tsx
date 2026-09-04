import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Box, Card, CardContent, Chip, CircularProgress, Divider, Grid, LinearProgress, Paper,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, ToggleButton, ToggleButtonGroup,
  Typography, useMediaQuery, useTheme,
} from "@mui/material";
import TrendingDownRoundedIcon from "@mui/icons-material/TrendingDownRounded";
import TrendingUpRoundedIcon from "@mui/icons-material/TrendingUpRounded";
import AccountBalanceWalletRoundedIcon from "@mui/icons-material/AccountBalanceWalletRounded";
import AccountBalanceRoundedIcon from "@mui/icons-material/AccountBalanceRounded";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import StorefrontRoundedIcon from "@mui/icons-material/StorefrontRounded";
import { dashboardApi } from "../../services/dashboardApi";
import { useOrganization } from "../../app/OrganizationContext";
import type { DashboardData } from "../../types/dashboard";

const money = (value: string | number) => Number(value || 0).toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const dateValue = (days: number) => new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

function MetricCard({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: string }) {
  return <Card sx={{ height: "100%", border: "1px solid", borderColor: "divider", boxShadow: "none" }}><CardContent>
    <Stack direction="row" justifyContent="space-between" alignItems="flex-start"><Box><Typography variant="body2" color="text.secondary">{label}</Typography><Typography variant="h5" sx={{ mt: 1, fontWeight: 700 }}>{value}</Typography></Box><Box sx={{ p: 1, borderRadius: 2, bgcolor: `${tone}18`, color: tone, display: "flex" }}>{icon}</Box></Stack>
  </CardContent></Card>;
}

function TrendChart({ data }: { data: DashboardData["income_vs_expense"] }) {
  const max = Math.max(...data.flatMap((point) => [Number(point.income), Number(point.expenses)]), 1);
  return <Stack spacing={1.5}>{data.slice(-8).map((point) => <Box key={point.period}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{point.period.slice(5)}</Typography><Typography variant="caption" color="text.secondary">{money(point.income)} / {money(point.expenses)}</Typography></Stack><Stack direction="row" spacing={.5} sx={{ height: 8, mt: .5 }}><Box sx={{ width: `${Number(point.income) / max * 100}%`, bgcolor: "success.main", borderRadius: 1 }} /><Box sx={{ width: `${Number(point.expenses) / max * 100}%`, bgcolor: "error.main", borderRadius: 1 }} /></Stack></Box>)}</Stack>;
}

function CategoryChart({ data }: { data: DashboardData["expenses_by_category"] }) {
  const max = Math.max(...data.map((row) => Number(row.amount)), 1);
  return <Stack spacing={1.5}>{data.slice(0, 6).map((row) => <Box key={row.category_id}><Stack direction="row" justifyContent="space-between"><Typography variant="body2" noWrap sx={{ maxWidth: "65%" }}>{row.category}</Typography><Typography variant="body2" fontWeight={600}>{money(row.amount)}</Typography></Stack><LinearProgress variant="determinate" value={Number(row.amount) / max * 100} sx={{ mt: .5, height: 6, borderRadius: 2 }} /></Box>)}</Stack>;
}

function CashFlowChart({ data }: { data: DashboardData["cash_flow"] }) {
  const max = Math.max(...data.flatMap((point) => [Number(point.receipts), Number(point.payments)]), 1);
  return <Stack spacing={1.5}>{data.slice(-8).map((point) => <Box key={point.period}><Stack direction="row" justifyContent="space-between"><Typography variant="caption">{point.period}</Typography><Typography variant="caption" color="text.secondary">Net {money(point.net)}</Typography></Stack><Stack direction="row" spacing={.5} sx={{ height: 8, mt: .5 }}><Box sx={{ width: `${Number(point.receipts) / max * 100}%`, bgcolor: "info.main", borderRadius: 1 }} /><Box sx={{ width: `${Number(point.payments) / max * 100}%`, bgcolor: "warning.main", borderRadius: 1 }} /></Stack></Box>)}</Stack>;
}

function BranchChart({ data }: { data: DashboardData["branch_comparison"] }) {
  const max = Math.max(...data.map((point) => Number(point.income)), 1);
  return <Stack spacing={1.5}>{data.slice(0, 6).map((point) => <Box key={point.branch_id ?? point.branch}><Stack direction="row" justifyContent="space-between"><Typography variant="body2" noWrap>{point.branch}</Typography><Typography variant="body2" fontWeight={600}>{money(point.net)}</Typography></Stack><LinearProgress variant="determinate" value={Number(point.income) / max * 100} sx={{ mt: .5, height: 6, borderRadius: 2 }} /></Box>)}</Stack>;
}

function TransactionTable({ data }: { data: DashboardData["recent_transactions"] }) {
  return <Table size="small"><TableHead><TableRow><TableCell>Transaction</TableCell><TableCell>Date</TableCell><TableCell align="right">Amount</TableCell></TableRow></TableHead><TableBody>{data.map((row) => <TableRow key={row.id}><TableCell><Typography variant="body2" fontWeight={600}>{row.transaction_number}</Typography><Typography variant="caption" color="text.secondary">{row.description || "General transaction"}</Typography></TableCell><TableCell>{row.transaction_date}</TableCell><TableCell align="right">{money(row.amount)}</TableCell></TableRow>)}</TableBody></Table>;
}

function OutstandingTable({ rows, label }: { rows: DashboardData["customer_outstanding"]; label: string }) {
  return <Table size="small"><TableHead><TableRow><TableCell>{label}</TableCell><TableCell align="right">Outstanding</TableCell></TableRow></TableHead><TableBody>{rows.slice(0, 6).map((row) => <TableRow key={row.id}><TableCell><Typography variant="body2" fontWeight={600}>{row.name}</Typography><Typography variant="caption" color="text.secondary">{row.code}</Typography></TableCell><TableCell align="right">{money(row.outstanding)}</TableCell></TableRow>)}</TableBody></Table>;
}

function DashboardContent({ data }: { data: DashboardData }) {
  const cards = [
    ["Income", money(data.cards.income), <TrendingUpRoundedIcon />, "#15803d"],
    ["Expenses", money(data.cards.expenses), <TrendingDownRoundedIcon />, "#dc2626"],
    ["Cash balance", money(data.cards.cash_balance), <AccountBalanceWalletRoundedIcon />, "#2563eb"],
    ["Bank balance", money(data.cards.bank_balance), <AccountBalanceRoundedIcon />, "#7c3aed"],
    ["Receivables", money(data.cards.receivables), <PeopleAltRoundedIcon />, "#0891b2"],
    ["Payables", money(data.cards.payables), <StorefrontRoundedIcon />, "#c2410c"],
  ];
  return <Stack spacing={3}><Grid container spacing={2}>{cards.map(([label, value, icon, tone]) => <Grid item xs={12} sm={6} md={4} lg={2} key={label as string}><MetricCard label={label as string} value={value as string} icon={icon as ReactNode} tone={tone as string} /></Grid>)}</Grid>
    <Grid container spacing={2}><Grid item xs={12} lg={7}><Card sx={{ height: "100%", boxShadow: "none", border: "1px solid", borderColor: "divider" }}><CardContent><Stack direction="row" justifyContent="space-between" mb={2}><Box><Typography variant="h6">Income vs expenses</Typography><Typography variant="body2" color="text.secondary">Monthly reporting period</Typography></Box><Stack direction="row" spacing={1}><Chip size="small" label="Income" color="success" variant="outlined" /><Chip size="small" label="Expense" color="error" variant="outlined" /></Stack></Stack><TrendChart data={data.income_vs_expense} /></CardContent></Card></Grid><Grid item xs={12} lg={5}><Card sx={{ height: "100%", boxShadow: "none", border: "1px solid", borderColor: "divider" }}><CardContent><Typography variant="h6">Expenses by category</Typography><Typography variant="body2" color="text.secondary" mb={2}>Posted expenses</Typography><CategoryChart data={data.expenses_by_category} /></CardContent></Card></Grid></Grid>
    <Grid container spacing={2}><Grid item xs={12} md={6}><Card sx={{ height: "100%", boxShadow: "none", border: "1px solid", borderColor: "divider" }}><CardContent><Typography variant="h6">Monthly cash flow</Typography><Typography variant="body2" color="text.secondary" mb={2}>Receipts, payments and net movement</Typography><CashFlowChart data={data.cash_flow} /></CardContent></Card></Grid><Grid item xs={12} md={6}><Card sx={{ height: "100%", boxShadow: "none", border: "1px solid", borderColor: "divider" }}><CardContent><Typography variant="h6">Branch comparison</Typography><Typography variant="body2" color="text.secondary" mb={2}>Authorized branches only</Typography><BranchChart data={data.branch_comparison} /></CardContent></Card></Grid></Grid>
    <Grid container spacing={2}><Grid item xs={12} lg={7}><Card sx={{ boxShadow: "none", border: "1px solid", borderColor: "divider", overflow: "auto" }}><CardContent><Typography variant="h6" mb={1}>Recent transactions</Typography><TransactionTable data={data.recent_transactions} /></CardContent></Card></Grid><Grid item xs={12} lg={5}><Card sx={{ boxShadow: "none", border: "1px solid", borderColor: "divider", overflow: "auto" }}><CardContent><Typography variant="h6" mb={1}>Pending approvals</Typography>{data.pending_approvals.length ? <Stack divider={<Divider />} spacing={1}>{data.pending_approvals.map((row) => <Stack key={row.id} direction="row" justifyContent="space-between"><Box><Typography variant="body2" fontWeight={600}>{row.number}</Typography><Typography variant="caption" color="text.secondary">{row.kind} · {row.date}</Typography></Box><Typography variant="body2" fontWeight={600}>{money(row.amount)}</Typography></Stack>)}</Stack> : <Typography color="text.secondary">Nothing waiting for approval.</Typography>}</CardContent></Card></Grid></Grid>
    <Card sx={{ boxShadow: "none", border: "1px solid", borderColor: "divider", overflow: "auto" }}><CardContent><Typography variant="h6" mb={1}>Recent expenses</Typography><Table size="small"><TableHead><TableRow><TableCell>Expense</TableCell><TableCell>Category</TableCell><TableCell>Date</TableCell><TableCell align="right">Amount</TableCell></TableRow></TableHead><TableBody>{data.recent_expenses.map((row) => <TableRow key={row.id}><TableCell>{row.expense_number}</TableCell><TableCell>{row.category}</TableCell><TableCell>{row.date}</TableCell><TableCell align="right">{money(row.amount)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
    <Grid container spacing={2}><Grid item xs={12} md={6}><Card sx={{ boxShadow: "none", border: "1px solid", borderColor: "divider", overflow: "auto" }}><CardContent><Typography variant="h6" mb={1}>Customer outstanding</Typography><OutstandingTable rows={data.customer_outstanding} label="Customer" /></CardContent></Card></Grid><Grid item xs={12} md={6}><Card sx={{ boxShadow: "none", border: "1px solid", borderColor: "divider", overflow: "auto" }}><CardContent><Typography variant="h6" mb={1}>Vendor outstanding</Typography><OutstandingTable rows={data.vendor_outstanding} label="Vendor" /></CardContent></Card></Grid></Grid>
  </Stack>;
}

export function DashboardPage() {
  const { companyId, branchId } = useOrganization();
  const mobile = useMediaQuery(useTheme().breakpoints.down("sm"));
  const [range, setRange] = useState<"7" | "30" | "90">("30");
  const query = useQuery({ queryKey: ["dashboard", companyId, branchId, range], queryFn: () => dashboardApi.summary({ companyId, branchId: branchId || undefined, startDate: dateValue(Number(range) - 1), endDate: dateValue(0) }), enabled: Boolean(companyId), staleTime: 30000 });
  const heading = useMemo(() => mobile ? "Overview" : "Management dashboard", [mobile]);
  if (!companyId) return <Alert severity="info">Select a company to view the management dashboard.</Alert>;
  if (query.isLoading) return <Box sx={{ display: "flex", justifyContent: "center", p: 8 }}><CircularProgress /></Box>;
  if (query.isError || !query.data) return <Alert severity="error">Dashboard data could not be loaded. Check your access and reporting period.</Alert>;
  return <Stack spacing={3}><Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}><Box><Typography variant={mobile ? "h5" : "h4"} fontWeight={700}>{heading}</Typography><Typography color="text.secondary">A clear view of your organization&apos;s financial health.</Typography></Box><ToggleButtonGroup exclusive size="small" value={range} onChange={(_, value) => value && setRange(value)}><ToggleButton value="7">7 days</ToggleButton><ToggleButton value="30">30 days</ToggleButton><ToggleButton value="90">90 days</ToggleButton></ToggleButtonGroup></Stack><Paper sx={{ p: { xs: 1.5, sm: 2 }, bgcolor: "primary.main", color: "primary.contrastText", borderRadius: 3 }}><Typography variant="body2" sx={{ opacity: .8 }}>Reporting period</Typography><Typography fontWeight={600}>{query.data.start_date} — {query.data.end_date}</Typography></Paper><DashboardContent data={query.data} /></Stack>;
}
