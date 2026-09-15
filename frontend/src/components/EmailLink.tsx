/**
 * An email address, displayed as an envelope.
 *
 * The address is gone from the page, so it travels in the title - hovering the
 * icon still says where the mail is going, and the aria-label names the link,
 * which would otherwise be an unnamed link with no text in it.
 */
export function EmailLink({
  address,
  name,
}: {
  address: string;
  name?: string;
}) {
  return (
    <a
      className="icon-link"
      href={`mailto:${address}`}
      title={address}
      aria-label={name ? `Email ${name}` : address}
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
        <rect x="1.25" y="3.25" width="13.5" height="9.5" rx="1.25" />
        <path d="M2 4.75 8 9l6-4.25" />
      </svg>
    </a>
  );
}
