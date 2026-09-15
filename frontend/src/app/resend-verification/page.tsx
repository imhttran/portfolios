"use client";

import { useState, type FormEvent } from "react";
import { LOGIN_PATH, submitEmailForm } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { SITE } from "@/lib/site";

export default function ResendVerificationPage() {
  const [busy, setBusy] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submitEmailForm(
      event.currentTarget,
      "/api/resend-verification",
      setBusy,
    );
  };

  return (
    <div className="login-container">
      <PageTitle title={`Resend verification | ${SITE.name}`} />
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Resend verification</h1>
        <p>We&apos;ll send a new link to confirm your email.</p>

        <div className="input-group">
          <label htmlFor="email">Email</label>
          <input
            type="email"
            id="email"
            name="email"
            placeholder="Enter your email"
            required
          />
        </div>

        <button type="submit" className="login-button" disabled={busy}>
          {busy ? "Sending..." : "Send a new link"}
        </button>

        <div className="form-footer">
          <p>
            <a href={LOGIN_PATH}>Back to sign in</a>
          </p>
        </div>
      </form>
    </div>
  );
}
