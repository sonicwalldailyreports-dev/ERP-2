import { Alert, Snackbar } from "@mui/material";
import { createContext, useContext, useState, type ReactNode } from "react";

type Notice = { message: string; severity: "success" | "info" | "warning" | "error" };
const NotificationContext = createContext<{ notify: (notice: Notice) => void } | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<Notice | null>(null);
  return (
    <NotificationContext.Provider value={{ notify: setNotice }}>
      {children}
      <Snackbar open={Boolean(notice)} autoHideDuration={4000} onClose={() => setNotice(null)}>
        <Alert severity={notice?.severity} onClose={() => setNotice(null)} variant="filled">
          {notice?.message}
        </Alert>
      </Snackbar>
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const context = useContext(NotificationContext);
  if (!context) throw new Error("useNotification must be used within NotificationProvider");
  return context;
}

