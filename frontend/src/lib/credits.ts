// The credit strip under an album title.

type Credited = {
  credit?: string | null;
  description?: string | null;
  artistName?: string | null;
};

function normalise(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

// What the strip should say after the artist's name, or null for nothing.
//
// The album already names its owner beside this text, so a credit that just
// repeats the owner is dropped: an album credited to the person who owns it
// would otherwise read "ETHAN TRAN · ETHAN TRAN". Anything else - a guest
// photographer, a collection name - still shows, which is what the field is for.
export function creditFor(album: Credited): string | null {
  const credit = album.credit?.trim();
  if (credit && normalise(credit) !== normalise(album.artistName ?? "")) {
    return credit;
  }
  return album.description?.trim() || null;
}
