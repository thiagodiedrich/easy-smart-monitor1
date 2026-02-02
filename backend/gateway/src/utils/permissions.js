/**
 * Permissões por role (RBAC) e validação de acesso.
 */

function getRoleName(role) {
  if (!role) return null;
  if (typeof role === 'string') return role;
  if (Array.isArray(role)) {
    if (role.includes(0) || role.includes('0')) return 'super';
    if (role.includes('admin')) return 'admin';
    if (role.includes('manager')) return 'manager';
    if (role.includes('user')) return 'user';
    if (role.includes('viewer')) return 'user'; // Fallback
    if (role.includes('device')) return 'device';
    return null;
  }
  if (typeof role === 'object') {
    if (role[0] === true || role['0'] === true || role.super === true) return 'super';
    if (role.role) return role.role;
    if (role.name) return role.name;
    return null;
  }
  return null;
}

const ROLE_PERMISSIONS = {
  super: ['*'],
  admin: [
    'tenant.*',
    'analytics.*',
    'telemetry.*',
    'health.*',
    'auth.*',
    'admin.*',
  ],
  manager: [
    'tenant.organizations.read',
    'tenant.workspaces.*',
    'tenant.equipments.*',
    'tenant.sensors.*',
    'tenant.alerts.*',
    'tenant.webhooks.*',
    'tenant.limits.read',
    'tenant.usage.read',
    'tenant.alerts.history.read',
    'tenant.users.read',
    'tenant.users.create',
    'tenant.users.update',
    'tenant.users.password',
    'tenant.users.status',
    'analytics.*',
    'health.*',
    'auth.me',
  ],
  user: [
    'tenant.organizations.read',
    'tenant.workspaces.read',
    'tenant.equipments.read',
    'tenant.sensors.read',
    'tenant.alerts.read',
    'tenant.webhooks.read',
    'tenant.limits.read',
    'tenant.usage.read',
    'tenant.alerts.history.read',
    'tenant.users.read',
    'analytics.*',
    'health.*',
    'auth.me',
  ],
  viewer: [
    'tenant.organizations.read',
    'tenant.workspaces.read',
    'tenant.equipments.read',
    'tenant.sensors.read',
    'tenant.alerts.read',
    'tenant.webhooks.read',
    'tenant.limits.read',
    'tenant.usage.read',
    'tenant.alerts.history.read',
    'tenant.users.read',
    'analytics.*',
    'health.*',
    'auth.me',
  ],
  device: [
    'auth.device.login',
    'auth.refresh',
    'auth.me',
    'telemetry.bulk',
    'tenant.workspaces.read',
  ],
};

function extractRolePermissions(role) {
  if (role && typeof role === 'object' && Array.isArray(role.permissions)) {
    return role.permissions;
  }
  return null;
}

function matchesPermission(allowedPermission, requestedPermission) {
  if (allowedPermission === '*') return true;
  if (allowedPermission.endsWith('.*')) {
    const prefix = allowedPermission.slice(0, -1);
    return requestedPermission.startsWith(prefix);
  }
  return allowedPermission === requestedPermission;
}

export function getEffectivePermissions(role) {
  const roleName = getRoleName(role);
  const customPermissions = extractRolePermissions(role);
  return customPermissions || ROLE_PERMISSIONS[roleName] || [];
}

export function hasPermission(request, permission) {
  if (!permission) return true;
  const roleName = getRoleName(request.user?.role);
  if (roleName === 'super') {
    return true;
  }
  if (permission.startsWith('admin.') && Number(request.user?.tenant_id) !== 0) {
    return false;
  }
  const permissions = getEffectivePermissions(request.user?.role);
  return permissions.some((allowed) => matchesPermission(allowed, permission));
}
