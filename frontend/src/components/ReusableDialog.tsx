import { Dialog, DialogContent, DialogTitle, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import type { ReactNode } from "react";

export function ReusableDialog({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
  return <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm"><DialogTitle>{title}<IconButton onClick={onClose} sx={{ float: "right" }} aria-label="Close"><CloseIcon /></IconButton></DialogTitle><DialogContent>{children}</DialogContent></Dialog>;
}

