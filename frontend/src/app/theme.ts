import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    primary: { main: "#335cff" },
    secondary: { main: "#11b8a6" },
    background: { default: "#f5f7fb", paper: "#ffffff" },
    text: { primary: "#172033", secondary: "#667085" },
  },
  typography: {
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    h4: { fontWeight: 750, letterSpacing: "-0.03em" },
    h6: { fontWeight: 700 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiCard: { styleOverrides: { root: { border: "1px solid #e8ebf2" } } },
  },
});

