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
    "Most of these were made without asking anyone to hold still. Nothing here is arranged.",
  // The About band on the landing page. Two or three sentences, in your voice.
  bio: "A creative guy with a camera, too many ideas, good taste, and just enough existential crisis to turn it all into art.",
  email: "tom.tran@email.com",
  // Optional: blank values are left out of the footer rather than shown empty.
  phone: "",
  instagram: "",
} as const;

// The longer version of the About section, below the one-line bio. Ethan's own
// words, not part of the editable profile - there's no field for it in
// /studio, so it's static copy rather than something an artist page's own
// data could override.
export const ABOUT_MORE: string[] = [
  "Ethan is a filmmaker/art kid who accidentally became an internet creator while trying to figure out how to be an artist. 😄",
  "His stuff sits somewhere between cinematography, photography, graphic design, art curation, and mildly existential thoughts about being creative. His own site says he likes highlighting artists and photographers who inspire him while talking about the struggles of creating through his Uncurated Thoughts series.",
  "There’s also a nice contradiction to the whole persona: the name is “uncurated,” but everything looks suspiciously well curated. 😂 His current bio philosophy is essentially make things even when they might suck, which fits the vibe: experiment first, worry about perfection later.",
  "And he’s moving beyond just “Instagram creator.” He’s doing cinematography/film work—he was DP on Two Sleepy People—along with poster/design work and branded cinematic projects.",
];

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
