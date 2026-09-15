import { LOGIN_PATH } from "@/lib/api";
import { EmailLink } from "@/components/EmailLink";
import { InstagramLink } from "@/components/InstagramLink";

/**
 * The sign-off at the bottom of every page: whose site this is, how to reach
 * them, and the copyright line. One component so the four pages that show it
 * can't drift apart on what it says.
 */
export function SiteFooter({
  name,
  role,
  email,
  instagram,
  showSignIn = false,
}: {
  name: string;
  role: string;
  email: string;
  instagram?: string | null;
  showSignIn?: boolean;
}) {
  return (
    <footer className="site-footer">
      <span>
        {name} — {role}
      </span>
      <span>
        <EmailLink address={email} name={name} />
        {instagram ? (
          <>
            {" · "}
            <InstagramLink handle={instagram} name={name} />
          </>
        ) : null}
        {showSignIn ? (
          <>
            {" · "}
            <a href={LOGIN_PATH}>Sign in</a>
          </>
        ) : null}
      </span>
      <span>
        © {new Date().getFullYear()} {name}. All rights reserved.
      </span>
    </footer>
  );
}
