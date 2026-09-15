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
  role: "Photographer, DP",
  location: "New York, NY",
  // The hero statement. One idea, plainly said - not a tagline.
  statement:
    "A creative guy with a camera, too many ideas, good taste, and just enough existential crisis to turn it all into art.",
  // The line under the statement, in the hero itself.
  bio: "Most of these were made without asking anyone to hold still. Nothing here is arranged.",
  // The longer About section, below the one-line bio. Paragraphs are blank-line
  // separated (see splitParagraphs) - the same shape the /studio textarea and
  // the artist_profiles.about column use, so a page never has to know whether
  // this came from here or from the API.
  about:
    "Ethan is a filmmaker/art kid who became an internet creator while trying to figure out how to be an artist. 😄\n\nHis stuff sits somewhere between cinematography, photography, graphic design, art curation, and mildly existential thoughts about being creative. His own site says he likes highlighting artists and photographers who inspire him while talking about the struggles of creating through his Uncurated Thoughts series.\n\nThere’s also a nice contradiction to the whole persona: the name is “uncurated,” but everything looks suspiciously well curated. 😂 His current bio philosophy is essentially make things even when they might suck, which fits the vibe: experiment first, worry about perfection later.\n\nAnd he’s moving beyond just “Instagram creator.” He’s doing cinematography/film work—he was DP on Two Sleepy People—along with poster/design work and branded cinematic projects.",
  email: "tom.tran@email.com",
  // Optional: blank values are left out of the footer rather than shown empty.
  phone: "",
  instagram: "",
} as const;

// The About section's paragraphs are stored as one blank-line-separated blob
// (see artist_profiles.about) rather than a list column, so the page splits it
// back apart to render. An empty string yields no paragraphs, so callers can
// treat that as "no About section" without a separate check.
export function splitParagraphs(about: string): string[] {
  return about
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export type SiteCopy = {
  slug: string;
  name: string;
  role: string;
  location: string;
  statement: string;
  bio: string;
  about: string;
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
  about: string;
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
    about: profile.about || SITE.about,
    email: profile.contactEmail || SITE.email,
    phone: profile.phone ?? SITE.phone,
    instagram: profile.instagram ?? SITE.instagram,
  };
}
