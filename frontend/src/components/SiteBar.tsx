import type { ReactNode } from "react";
import { SignOut } from "@/components/SignOut";
import { ThemeToggle } from "@/components/ThemeToggle";

/**
 * The strip at the top of every page: who this site is, then its navigation.
 *
 * ``over`` floats it on top of a hero photograph instead of giving it a row of
 * its own. The theme switch and the sign-out link belong to the bar rather than
 * to each page, so no page can leave a visitor without a way out.
 */
export function SiteBar({
  name,
  role,
  links,
  over = false,
}: {
  name: string;
  role: string;
  links: { href: string; label: ReactNode }[];
  over?: boolean;
}) {
  return (
    <header className={`site-bar${over ? " site-bar--over" : ""}`}>
      <a className="site-identity" href="/">
        <span className="site-name">{name}</span>
        <span className="site-role">{role}</span>
      </a>
      <nav className="site-nav">
        {links.map((link) => (
          <a key={link.href} href={link.href}>
            {link.label}
          </a>
        ))}
        <ThemeToggle />
        <SignOut />
      </nav>
    </header>
  );
}
