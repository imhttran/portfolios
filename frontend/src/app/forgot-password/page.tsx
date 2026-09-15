"use client";

import { useState, type FormEvent } from "react";
import { LOGIN_PATH, submitEmailForm } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { SITE } from "@/lib/site";

export default function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submitEmailForm(event.currentTarget, "/api/forgot-password", setBusy);
  };

  return (
    <div className="login-container">
      <PageTitle title={`Reset your password | ${SITE.name}`} />
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Reset your password</h1>
        <p>We’ll email you a link to set a new one.</p>

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
          {busy ? "Sending…" : "Email me a link"}
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
