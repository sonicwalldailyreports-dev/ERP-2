import { Card, CardContent, Skeleton, Stack } from "@mui/material";

export function LoadingState() {
  return <Stack spacing={2}>{[1, 2, 3].map((item) => <Card key={item}><CardContent><Skeleton width="35%" /><Skeleton width="80%" /><Skeleton width="60%" /></CardContent></Card>)}</Stack>;
}

