"use client";

import { useState, type FormEvent } from "react";
import { LOGIN_PATH, confirmedPasswordOrAlert, submitForm } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { SITE } from "@/lib/site";

export default function ResetPasswordPage() {
  const [busy, setBusy] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password"));
    const confirmPassword = String(data.get("confirmPassword"));

    if (!confirmedPasswordOrAlert(password, confirmPassword)) return;

    void submitForm<{ token: string; message: string }>(
      "/api/reset-password",
      {
        token: new URLSearchParams(window.location.search).get("token"),
        password,
      },
      (result) => {
        localStorage.setItem("auth_token", result.token);
        alert(result.message);
        window.location.href = "/dashboard";
      },
      setBusy,
    );
  };

  return (
    <div className="login-container">
      <PageTitle title={`Set a new password | ${SITE.name}`} />
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Set a new password</h1>
        <p>You’ll be signed in once it’s saved.</p>

        <div className="input-group">
          <label htmlFor="password">New password</label>
          <input
            type="password"
            id="password"
            name="password"
            placeholder="Min 8 chars, 1 upper, 1 num, 1 special"
            required
          />
        </div>

        <div className="input-group">
          <label htmlFor="confirm-password">Confirm password</label>
          <input
            type="password"
            id="confirm-password"
            name="confirmPassword"
            placeholder="Re-enter your password"
            required
          />
        </div>

        <button type="submit" className="login-button" disabled={busy}>
          {busy ? "Saving…" : "Save password"}
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
