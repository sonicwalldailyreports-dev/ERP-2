import { useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";

export function LoginPage() {
  const { login } = useAuth(); const navigate = useNavigate(); const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState("");
  const submit = async () => { try { setError(""); await login(username, password); navigate("/", { replace: true }); } catch { setError("Unable to sign in with those credentials."); } };
  return <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2 }}><Card sx={{ width: "100%", maxWidth: 420 }}><CardContent sx={{ p: { xs: 3, sm: 5 } }}><Typography variant="h4" gutterBottom>Welcome back</Typography><Typography color="text.secondary" sx={{ mb: 3 }}>Sign in to your office workspace.</Typography><Stack spacing={2}>{error && <Alert severity="error">{error}</Alert>}<TextField label="Email" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" fullWidth /><TextField label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" fullWidth /><Button variant="contained" size="large" disabled={!username || !password} onClick={submit}>Sign in</Button></Stack></CardContent></Card></Box>;
}
