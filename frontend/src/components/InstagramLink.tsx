/**
 * An Instagram handle, displayed as the glyph.
 *
 * The handle is normalised on the way in - it may have been stored with a
 * leading @ - and that clean form is what the profile URL is built from. The
 * address travels in the title, since the handle is gone from the page.
 */
export function InstagramLink({
  handle,
  name,
}: {
  handle: string;
  name?: string;
}) {
  const handle_ = handle.replace(/^@/, "");
  return (
    <a
      className="icon-link"
      href={`https://www.instagram.com/${handle_}/`}
      title={`@${handle_}`}
      aria-label={name ? `${name} on Instagram` : `Instagram: @${handle_}`}
      target="_blank"
      rel="noreferrer"
    >
      <svg
        width="1em"
        height="1em"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        <rect x="1.25" y="1.25" width="13.5" height="13.5" rx="3.75" />
        <circle cx="8" cy="8" r="3.1" />
        <circle cx="11.6" cy="4.4" r="0.55" fill="currentColor" stroke="none" />
      </svg>
    </a>
  );
}
