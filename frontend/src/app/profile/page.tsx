"use client";

import { type FormEvent } from "react";
import { submitAuthedForm } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { SITE } from "@/lib/site";

export default function ProfilePage() {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void submitAuthedForm("/api/profile", {
      firstName: data.get("firstName"),
      lastName: data.get("lastName"),
    });
  };

  return (
    <div className="login-container">
      <PageTitle title={`Your name | ${SITE.name}`} />
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Your name</h1>
        <p>Saved to your account.</p>

        <div className="input-group">
          <label htmlFor="first-name">First name</label>
          <input type="text" id="first-name" name="firstName" required />
        </div>

        <div className="input-group">
          <label htmlFor="last-name">Last name</label>
          <input type="text" id="last-name" name="lastName" required />
        </div>

        <button type="submit" className="login-button">
          Save
        </button>
      </form>
    </div>
  );
}
