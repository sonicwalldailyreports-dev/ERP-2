import { FormControl, InputLabel, MenuItem, Select, Stack } from "@mui/material";
import { useOrganization } from "../app/OrganizationContext";

export function OrganizationSelectors() {
  const { companies, branches, companyId, branchId, setCompanyId, setBranchId } = useOrganization();
  return <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ minWidth: { sm: 380 } }}>
    <FormControl size="small" sx={{ minWidth: 180 }}><InputLabel>Company</InputLabel><Select value={companyId} label="Company" onChange={(event) => setCompanyId(event.target.value)}><MenuItem value="">Select company</MenuItem>{companies.map((company) => <MenuItem key={company.id} value={company.id}>{company.name}</MenuItem>)}</Select></FormControl>
    <FormControl size="small" sx={{ minWidth: 180 }} disabled={!companyId}><InputLabel>Branch</InputLabel><Select value={branchId} label="Branch" onChange={(event) => setBranchId(event.target.value)}><MenuItem value="">All branches</MenuItem>{branches.map((branch) => <MenuItem key={branch.id} value={branch.id}>{branch.name}</MenuItem>)}</Select></FormControl>
  </Stack>;
}
