// Every word on the public pages that isn't a photo's own title lives here.
//
// These are DEFAULTS. A artist can edit the same fields in /studio, and
// whatever they save takes precedence — this file is what a site shows before
// anyone has logged in, and it keeps the pages renderable if the API is down.
export const SITE = {
  // Empty until a profile is loaded; the landing uses it to show one artist's
  // work rather than everyone's.
  slug: "ethan-tran",
  name: "Ethan Tran",
  role: "Artist",
  location: "Austin, TX",
  // The hero statement. One idea, plainly said - not a tagline.
  statement:
    "Most of these were made without asking anyone to hold still. Nothing here is arranged.",
  // The About band on the landing page. Two or three sentences, in your voice.
  bio: "Placeholder. Say who you are, what you shoot, and who you shoot it for.",
  email: "you@example.com",
  // Optional: blank values are left out of the footer rather than shown empty.
  phone: "",
  instagram: "",
} as const;

export type SiteCopy = {
  slug: string;
  name: string;
  role: string;
  location: string;
  statement: string;
  bio: string;
  email: string;
  phone: string;
  instagram: string;
};

type ApiProfile = {
  slug: string;
  displayName: string;
  tagline: string;
  statement: string;
  bio: string;
  location: string;
  contactEmail: string;
  phone: string | null;
  instagram: string | null;
};

// One shape for the pages to render, whether it came from the API or from the
// defaults above - so no component has to know which.
export function copyFrom(profile: ApiProfile | null | undefined): SiteCopy {
  if (!profile) return SITE;
  return {
    slug: profile.slug || SITE.slug,
    name: profile.displayName || SITE.name,
    role: profile.tagline || SITE.role,
    location: profile.location || SITE.location,
    statement: profile.statement || SITE.statement,
    bio: profile.bio || SITE.bio,
    email: profile.contactEmail || SITE.email,
    phone: profile.phone ?? SITE.phone,
    instagram: profile.instagram ?? SITE.instagram,
  };
}
