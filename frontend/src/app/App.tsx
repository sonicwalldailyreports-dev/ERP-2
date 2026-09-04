import { Routes, Route, Outlet } from "react-router-dom";
import { Card, CardContent, Typography } from "@mui/material";
import { AppLayout } from "../layouts/AppLayout";
import { EmptyState } from "../components/EmptyState";
import { CompanyManagement } from "../features/companies/CompanyManagement";
import { BranchManagement } from "../features/branches/BranchManagement";
import { LoginPage } from "../features/auth/LoginPage";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { OrganizationProvider } from "./OrganizationContext";
import { RoleManagement } from "../features/roles/RoleManagement";
import { UserManagement } from "../features/users/UserManagement";
import { CustomerManagement } from "../features/customers/CustomerManagement";
import { CustomerDetails } from "../features/customers/CustomerDetails";
import { VendorManagement } from "../features/vendors/VendorManagement";
import { VendorDetails } from "../features/vendors/VendorDetails";
import { CashBookPage } from "../features/cashbook/CashBookPage";
import { ExpensePage } from "../features/expenses/ExpensePage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { AuditLogPage } from "../features/audit/AuditLogPage";

const pages: Record<string, string> = {
  customers: "Customers", vendors: "Vendors", "cash-book": "Cash Book", expenses: "Expenses", reports: "Reports",
  users: "Users", roles: "Roles", audit: "Audit logs", settings: "Settings",
};

function Dashboard() {
  return <DashboardPage />;
}

function PlaceholderPage({ title }: { title: string }) {
  return <><Typography variant="h4" gutterBottom>{title}</Typography><Typography color="text.secondary" sx={{ mb: 3 }}>This workspace is ready for the {title.toLowerCase()} module.</Typography><Card><CardContent><EmptyState title={`${title} is not configured`} description="Business functionality will be introduced in a later phase." /></CardContent></Card></>;
}

function ProtectedShell() {
  return <OrganizationProvider><AppLayout><Outlet /></AppLayout></OrganizationProvider>;
}

export function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<ProtectedRoute />}><Route element={<ProtectedShell />}><Route path="/" element={<Dashboard />} /><Route path="/companies" element={<CompanyManagement />} /><Route path="/branches" element={<BranchManagement />} /><Route path="/customers" element={<CustomerManagement />} /><Route path="/customers/:customerId" element={<CustomerDetails />} /><Route path="/vendors" element={<VendorManagement />} /><Route path="/vendors/:vendorId" element={<VendorDetails />} /><Route path="/cash-book" element={<CashBookPage />} /><Route path="/expenses" element={<ExpensePage />} />  {Object.entries(pages).filter(([path]) => path !== "customers" && path !== "vendors" && path !== "cash-book" && path !== "expenses").map(([path, title]) => <Route key={path} path={`/${path}`} element={path === "roles" ? <RoleManagement /> : path === "users" ? <UserManagement /> : path === "audit" ? <AuditLogPage /> : <PlaceholderPage title={title} />} />)}<Route path="*" element={<PlaceholderPage title="Page not found" />} /></Route></Route></Routes>;
}
