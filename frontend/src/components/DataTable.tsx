import { Table, TableBody, TableCell, TableHead, TableRow, TableContainer, Paper, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { EmptyState } from "./EmptyState";

export function DataTable({ columns, rows = [] }: { columns: string[]; rows?: ReactNode[][] }) {
  if (!rows.length) return <EmptyState title="Nothing here yet" description="Records will appear here when this module is configured." />;
  return <TableContainer component={Paper} variant="outlined"><Table><TableHead><TableRow>{columns.map((column) => <TableCell key={column}><Typography fontWeight={700}>{column}</Typography></TableCell>)}</TableRow></TableHead><TableBody>{rows.map((row, index) => <TableRow key={index}>{row.map((cell, cellIndex) => <TableCell key={cellIndex}>{cell}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer>;
}

