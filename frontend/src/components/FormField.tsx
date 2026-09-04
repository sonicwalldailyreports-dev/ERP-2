import { TextField } from "@mui/material";
import { Controller, type Control, type FieldValues, type Path } from "react-hook-form";

export function FormField<T extends FieldValues>({ name, control, label }: { name: Path<T>; control: Control<T>; label: string }) {
  return <Controller name={name} control={control} render={({ field, fieldState }) => <TextField {...field} label={label} error={Boolean(fieldState.error)} helperText={fieldState.error?.message} fullWidth />} />;
}

