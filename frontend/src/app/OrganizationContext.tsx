import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { organizationApi } from "../services/organizationApi";
import type { Branch, Company } from "../types/organization";

type OrganizationContextValue = {
  companies: Company[]; branches: Branch[]; companyId: string; branchId: string;
  setCompanyId: (id: string) => void; setBranchId: (id: string) => void; isLoading: boolean;
};
const Context = createContext<OrganizationContextValue | null>(null);

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const [companyId, setCompany] = useState(localStorage.getItem("companyId") ?? "");
  const [branchId, setBranch] = useState(localStorage.getItem("branchId") ?? "");
  const companiesQuery = useQuery({ queryKey: ["companies"], queryFn: organizationApi.companies });
  const branchesQuery = useQuery({ queryKey: ["branches", companyId], queryFn: () => organizationApi.branches(companyId), enabled: Boolean(companyId) });
  const setCompanyId = (id: string) => { localStorage.setItem("companyId", id); setCompany(id); setBranchId(""); };
  const setBranchId = (id: string) => { localStorage.setItem("branchId", id); setBranch(id); };
  const value = useMemo(() => ({ companies: companiesQuery.data ?? [], branches: branchesQuery.data ?? [], companyId, branchId, setCompanyId, setBranchId, isLoading: companiesQuery.isLoading || branchesQuery.isLoading }), [companiesQuery.data, branchesQuery.data, companiesQuery.isLoading, branchesQuery.isLoading, companyId, branchId]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useOrganization() {
  const value = useContext(Context);
  if (!value) throw new Error("useOrganization must be used within OrganizationProvider");
  return value;
}
