import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from "@mui/material";

export function ConfirmDialog({
  open, title, description, onConfirm, onClose,
}: { open: boolean; title: string; description: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent><DialogContentText>{description}</DialogContentText></DialogContent>
      <DialogActions><Button onClick={onClose}>Cancel</Button><Button onClick={onConfirm} variant="contained" color="error">Confirm</Button></DialogActions>
    </Dialog>
  );
}

