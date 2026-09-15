"use client";

import { useEffect, useState } from "react";

// Sign out, from wherever the site header appears.
//
// Client-side by design: the session is a bearer token in localStorage and the
// server keeps no session table, so there is nothing to revoke. The device id is
// deliberately left alone - it is what lets the next login skip the 2FA step.
//
// The token only exists in the browser, so this shows nothing until after mount;
// the server render and the first client render stay identical.
export function SignOut({ className }: { className?: string }) {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(Boolean(localStorage.getItem("auth_token")));
  }, []);

  if (!signedIn) return null;

  return (
    <a
      className={className}
      href="/"
      onClick={(event) => {
        event.preventDefault();
        localStorage.removeItem("auth_token");
        // Back to the portfolio, where you are a visitor again. Sending this to
        // /login instead would land you on a form you did not ask for.
        window.location.href = "/";
      }}
    >
      Sign out
    </a>
  );
}
