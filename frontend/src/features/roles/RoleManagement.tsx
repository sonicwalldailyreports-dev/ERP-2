import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useOrganization } from "../../app/OrganizationContext";
import {
  usePermissions,
  useRoleMutations,
  useRolePermissions,
  useRoles,
  useUserOverrides,
  useUserRoleMutations,
} from "./useRoles";

export function RoleManagement() {
  const { companyId } = useOrganization();
  const rolesQuery = useRoles(companyId || undefined);
  const permissionsQuery = usePermissions();
  const { create, update, setPermissions } = useRoleMutations(companyId || undefined);
  const [selected, setSelected] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [permissionSearch, setPermissionSearch] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [userId, setUserId] = useState("");
  const [overridePermission, setOverridePermission] = useState("");
  const [overrideGranted, setOverrideGranted] = useState(true);
  const role = rolesQuery.data?.find((item) => item.id === selected);
  const rolePermissionsQuery = useRolePermissions(selected || undefined);
  const userRoles = useUserRoleMutations(userId);
  const overrides = useUserOverrides(userId);

  useEffect(() => {
    if (rolePermissionsQuery.data) {
      setSelectedPermissions(rolePermissionsQuery.data.map((item) => item.id));
    }
  }, [rolePermissionsQuery.data]);

  const filteredPermissions = useMemo(
    () =>
      permissionsQuery.data?.filter((permission) =>
        permission.code.includes(permissionSearch.toLowerCase()),
      ) ?? [],
    [permissionsQuery.data, permissionSearch],
  );

  const submit = async () => {
    const created = await create.mutateAsync({
      name,
      description,
      ...(companyId ? { company_id: companyId } : {}),
    });
    await setPermissions.mutateAsync({ id: created.id, permission_ids: selectedPermissions });
    setDialogOpen(false);
    setName("");
    setDescription("");
    setSelectedPermissions([]);
  };

  if (rolesQuery.isLoading || permissionsQuery.isLoading) return <Typography>Loading roles...</Typography>;
  if (rolesQuery.isError || permissionsQuery.isError) {
    return <Alert severity="error">Unable to load role configuration.</Alert>;
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <div>
          <Typography variant="h4">Roles</Typography>
          <Typography color="text.secondary">
            Manage roles and module.resource.action permissions.
          </Typography>
        </div>
        <Button
          variant="contained"
          disabled={!companyId}
          onClick={() => {
            setSelected("");
            setSelectedPermissions([]);
            setDialogOpen(true);
          }}
        >
          Create role
        </Button>
      </Stack>
      <Select
        value={selected}
        displayEmpty
        onChange={(event) => setSelected(event.target.value)}
        sx={{ maxWidth: 420 }}
      >
        <MenuItem value="">Select a role</MenuItem>
        {rolesQuery.data?.map((item) => (
          <MenuItem key={item.id} value={item.id}>
            {item.name}
            {item.is_system ? " (system)" : ""}
          </MenuItem>
        ))}
      </Select>
      {role && (
        <Stack spacing={2}>
          <Typography variant="h6">{role.name}</Typography>
          <Typography color="text.secondary">{role.description || "No description"}</Typography>
          <FormControlLabel
            control={
              <Checkbox
                checked={role.is_active}
                onChange={(event) => update.mutate({ id: role.id, is_active: event.target.checked })}
              />
            }
            label="Active"
          />
          <Typography variant="subtitle1">Permission matrix</Typography>
          <TextField
            size="small"
            label="Search permissions"
            value={permissionSearch}
            onChange={(event) => setPermissionSearch(event.target.value)}
          />
          <List>
            {filteredPermissions.map((permission) => (
              <ListItem key={permission.id} disablePadding>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={selectedPermissions.includes(permission.id)}
                      onChange={(event) =>
                        setSelectedPermissions((current) =>
                          event.target.checked
                            ? [...current, permission.id]
                            : current.filter((id) => id !== permission.id),
                        )
                      }
                    />
                  }
                  label={<ListItemText primary={permission.code} secondary={permission.description} />}
                />
              </ListItem>
            ))}
          </List>
          <Button variant="outlined" onClick={() => setPermissions.mutate({ id: role.id, permission_ids: selectedPermissions })}>
            Save permissions
          </Button>
          <Typography variant="subtitle1">Assign users</Typography>
          <TextField
            size="small"
            label="User ID"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            helperText="Enter the user's UUID"
          />
          <Button disabled={!userId} onClick={() => userRoles.assign.mutate(role.id)}>
            Assign selected role
          </Button>
          {userRoles.roles.data?.map((assigned) => (
            <Typography key={assigned.id} variant="body2">
              Assigned: {assigned.name}{" "}
              <Button size="small" onClick={() => userRoles.remove.mutate(assigned.id)}>
                Remove
              </Button>
            </Typography>
          ))}
          <Typography variant="subtitle1">User permission override</Typography>
          <Select
            size="small"
            value={overridePermission}
            displayEmpty
            onChange={(event) => setOverridePermission(event.target.value)}
          >
            <MenuItem value="">Select permission</MenuItem>
            {permissionsQuery.data?.map((permission) => (
              <MenuItem key={permission.id} value={permission.id}>
                {permission.code}
              </MenuItem>
            ))}
          </Select>
          <FormControlLabel
            control={
              <Checkbox
                checked={overrideGranted}
                onChange={(event) => setOverrideGranted(event.target.checked)}
              />
            }
            label="Grant permission (clear for deny)"
          />
          <Button
            disabled={!userId || !overridePermission}
            onClick={() =>
              overrides.create.mutate({ permission_id: overridePermission, is_granted: overrideGranted })
            }
          >
            Save override
          </Button>
          {overrides.query.data?.map((item) => (
            <Typography key={item.id} variant="body2">
              {permissionsQuery.data?.find((permission) => permission.id === item.permission_id)?.code}:{" "}
              {item.is_granted ? "grant" : "deny"}{" "}
              <Button size="small" onClick={() => overrides.deactivate.mutate(item.id)}>
                Remove
              </Button>
            </Typography>
          ))}
        </Stack>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create company role</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={name} onChange={(event) => setName(event.target.value)} required />
            <TextField
              label="Description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              multiline
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" disabled={!name.trim() || create.isPending} onClick={submit}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
