"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE, LOGIN_PATH } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { SITE } from "@/lib/site";

export default function VerifyPage() {
  const [message, setMessage] = useState("Please wait.");
  // Verify emails are links, so this can run twice in dev (StrictMode
  // double-invoked effects) — only fire the request once.
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    (async () => {
      const token = new URLSearchParams(window.location.search).get("token");
      try {
        const response = await fetch(
          `${API_BASE}/api/verify?token=${encodeURIComponent(token || "")}`,
        );
        const result = await response.json();
        if (response.ok) {
          setMessage(`${result.message} Redirecting to sign in…`);
          setTimeout(() => {
            window.location.href = LOGIN_PATH;
          }, 1500);
        } else {
          setMessage(result.message || "Verification failed.");
        }
      } catch {
        setMessage("Connection error. Is the backend running?");
      }
    })();
  }, []);

  return (
    <div className="login-container">
      <PageTitle title={`Verifying email | ${SITE.name}`} />
      <div className="login-form">
        <h1>Verifying your email</h1>
        <p id="verify-message">{message}</p>
      </div>
    </div>
  );
}
