// Ranked lowest to highest: a role satisfies a check for itself or anything below it.
// "artist" carries content powers (editing the site's public copy, and
// publishing work once uploads land) but nothing from staff, which is the
// user-management tier.
export const ROLES = ["client", "artist", "staff", "admin"] as const;

export type Role = (typeof ROLES)[number];

export function hasRole(userRole: string, minRole: Role): boolean {
  return (
    (ROLES as readonly string[]).indexOf(userRole) >= ROLES.indexOf(minRole)
  );
}
