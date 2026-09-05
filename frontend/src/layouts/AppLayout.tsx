import { useState, type ReactNode } from "react";
import { AppBar, Avatar, Box, Breadcrumbs, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText, Toolbar, Typography, useMediaQuery, useTheme } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import { NavLink, useLocation } from "react-router-dom";
import { OrganizationSelectors } from "../components/OrganizationSelectors";

const navigation = [
  ["Dashboard", "/", "▦"], ["Customers", "/customers", "◉"], ["Vendors", "/vendors", "◇"], ["Cash Book", "/cash-book", "▤"],
  ["Expenses", "/expenses", "−"], ["Reports", "/reports", "◒"], ["Users", "/users", "●"], ["Roles", "/roles", "◆"], ["Audit logs", "/audit", "≡"],
  ["Companies", "/companies", "▣"], ["Branches", "/branches", "⌂"], ["Settings", "/settings", "⚙"],
];

export function AppLayout({ children }: { children: ReactNode }) {
  const theme = useTheme(); const mobile = useMediaQuery(theme.breakpoints.down("md")); const [open, setOpen] = useState(false);
  const location = useLocation(); const current = navigation.find(([, path]) => path === location.pathname)?.[0] ?? "Page";
  const drawer = <Box sx={{ width: 260, p: 2 }}><Typography variant="h6" sx={{ px: 2, py: 2, color: "primary.main" }}>Office<span className="brand-dot">.</span></Typography><List>{navigation.map(([label, path, icon]) => <ListItemButton key={path} component={NavLink} to={path} onClick={() => setOpen(false)} selected={location.pathname === path} sx={{ borderRadius: 2, mb: .5 }}><ListItemIcon sx={{ minWidth: 36, fontSize: 20 }}>{icon}</ListItemIcon><ListItemText primary={label} /></ListItemButton>)}</List></Box>;
  return <Box sx={{ display: "flex", minHeight: "100vh" }}><AppBar position="fixed" color="inherit" elevation={0} sx={{ borderBottom: "1px solid #e8ebf2" }}><Toolbar><IconButton aria-label="Open navigation menu" onClick={() => setOpen(true)} sx={{ display: { md: "none" }, mr: 1 }}><MenuIcon /></IconButton><Typography sx={{ flexGrow: 1, fontWeight: 700 }}>{current}</Typography><OrganizationSelectors /><Avatar sx={{ bgcolor: "primary.main", width: 34, height: 34, ml: 1 }}>A</Avatar></Toolbar></AppBar>{mobile ? <Drawer open={open} onClose={() => setOpen(false)}>{drawer}</Drawer> : <Drawer variant="permanent" sx={{ "& .MuiDrawer-paper": { width: 260, boxSizing: "border-box", border: 0 } }}>{drawer}</Drawer>}<Box component="main" sx={{ flexGrow: 1, p: { xs: 2, sm: 3, md: 4 }, mt: 8, minWidth: 0 }}><Breadcrumbs sx={{ mb: 3 }}><HomeOutlinedIcon fontSize="small" /><Typography color="text.secondary">{current}</Typography></Breadcrumbs>{children}</Box></Box>;
}
