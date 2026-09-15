"use client";

import { useEffect, useState, type FormEvent } from "react";
import { API_BASE, LOGIN_PATH, callApi } from "@/lib/api";
import { SITE } from "@/lib/site";
import { hasRole } from "@/lib/roles";
import { AlbumManager } from "@/components/AlbumManager";
import { PageTitle } from "@/components/PageTitle";
import { SignOut } from "@/components/SignOut";

type Profile = {
  displayName: string;
  tagline: string;
  statement: string;
  bio: string;
  location: string;
  contactEmail: string;
  phone: string | null;
  instagram: string | null;
};

// The form works on strings throughout: a null in a controlled input would flip
// it to uncontrolled, and React warns about exactly that.
type FormProfile = Omit<Profile, "phone" | "instagram"> & {
  phone: string;
  instagram: string;
};

type Me = {
  id: number;
  email: string;
  role: string;
  mustChangePassword: boolean;
  hasProfile: boolean;
};

const EMPTY: FormProfile = {
  displayName: "",
  tagline: "",
  statement: "",
  bio: "",
  location: "",
  contactEmail: "",
  phone: "",
  instagram: "",
};

function fromApi(profile: Profile | null): FormProfile {
  if (!profile) return EMPTY;
  return {
    ...profile,
    phone: profile.phone ?? "",
    instagram: profile.instagram ?? "",
  };
}

export default function StudioPage() {
  const [token, setToken] = useState<string | null>(null);
  const [profile, setProfile] = useState<FormProfile>(EMPTY);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("auth_token");
    if (!stored) {
      window.location.href = LOGIN_PATH;
      return;
    }
    setToken(stored);

    (async () => {
      try {
        // Who am I, and may I be here. /api/me also carries the onboarding
        // flags the backend enforces, so a 403 here means "not yet".
        const me = await callApi<{ user: Me }>(
          stored,
          "/api/me",
          "GET",
          undefined,
          false,
        );
        if (!me) {
          localStorage.removeItem("auth_token");
          window.location.href = LOGIN_PATH;
          return;
        }
        if (me.user.mustChangePassword) {
          window.location.href = "/change-password";
          return;
        }
        if (!me.user.hasProfile) {
          window.location.href = "/profile";
          return;
        }
        if (!hasRole(me.user.role, "artist")) {
          setState("error");
          return;
        }

        const response = await fetch(`${API_BASE}/api/artist/profile/mine`, {
          headers: { Authorization: `Bearer ${stored}` },
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);
        setProfile(fromApi(data.profile));
        setState("ready");
      } catch {
        setState("error");
      }
    })();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;

    setSaving(true);
    setSaved(false);
    const result = await callApi(
      token,
      "/api/artist/profile",
      "PUT",
      profile,
      false,
    );
    setSaving(false);
    if (result) setSaved(true);
    else alert("Could not save the profile.");
  };

  const field = (
    name: keyof FormProfile,
    label: string,
    options?: { textarea?: boolean; hint?: string; type?: string },
  ) => (
    <div className="input-group">
      <label htmlFor={name}>{label}</label>
      {options?.textarea ? (
        <textarea
          id={name}
          value={profile[name]}
          rows={name === "statement" ? 2 : 4}
          onChange={(e) => setProfile({ ...profile, [name]: e.target.value })}
        />
      ) : (
        <input
          id={name}
          type={options?.type ?? "text"}
          value={profile[name]}
          onChange={(e) => setProfile({ ...profile, [name]: e.target.value })}
        />
      )}
      {options?.hint ? <p className="field-hint">{options.hint}</p> : null}
    </div>
  );

  return (
    <div className="studio-container">
      <PageTitle title={`Studio | ${profile.displayName || SITE.name}`} />
      <header className="page-header">
        <div>
          <h1>Studio</h1>
          <p>The words your portfolio shows.</p>
        </div>
        <span className="page-header-actions">
          <a className="header-link" href="/">
            View site
          </a>
          <a className="header-link" href="/dashboard">
            Dashboard
          </a>
          <SignOut className="header-link" />
        </span>
      </header>

      {state === "loading" ? (
        <p className="sheet-note">Loading...</p>
      ) : state === "error" ? (
        <p className="sheet-note">
          This page is for artists. Ask an admin to grant you the role.
        </p>
      ) : (
        <form className="studio-form" onSubmit={handleSubmit}>
          <fieldset>
            <legend className="mono">Who you are</legend>
            {field("displayName", "Name", {
              hint: "Shown in the top bar, in the footer, and as the page title.",
            })}
            {field("tagline", "Tagline", { hint: "The line under your name." })}
            {field("location", "Based in")}
            {field("contactEmail", "Contact email", { type: "email" })}
            {field("phone", "Phone", { hint: "Leave blank to omit it." })}
            {field("instagram", "Instagram", {
              hint: "Leave blank to omit it.",
            })}
          </fieldset>

          <fieldset>
            <legend className="mono">The words on the page</legend>
            {field("statement", "Statement", {
              textarea: true,
              hint: "One idea, plainly said. This is the largest type on the site.",
            })}
            {field("bio", "About", {
              textarea: true,
              hint: "Two or three sentences, in your own voice.",
            })}
          </fieldset>

          <div className="studio-actions">
            <button type="submit" className="login-button" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            {saved ? <span className="studio-saved">Saved</span> : null}
          </div>
        </form>
      )}

      {state === "ready" && token ? <AlbumManager token={token} /> : null}
    </div>
  );
}
