/**
 * The artist's handle, signed.
 *
 * A script face and a trailing stroke: the last letters let go and the line
 * keeps going, thinning out, so wherever this sits it reads as written rather
 * than printed. That trailing line is what a portrait's hair strands would pick
 * up - the signature flows out of the drawing instead of sitting on it like a
 * caption.
 *
 * aria-hidden: it signs work whose meaning is already on the page, and a screen
 * reader has no use for a handle announced out of nowhere.
 */
export function Signature({ handle }: { handle: string }) {
  return (
    <span className="signature" aria-hidden="true">
      <span className="signature-name">{handle}</span>
      <svg
        className="signature-swash"
        viewBox="0 0 220 26"
        preserveAspectRatio="none"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        {/* One line out of the last letter and away to the right, thinning; a
            second, fainter one beneath it, the way a pen comes back. */}
        <path
          d="M2 16 C 34 4, 62 22, 96 13 S 150 3, 218 16"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="M2 16 C 40 7, 74 20, 110 14 S 160 6, 214 15"
          stroke="currentColor"
          strokeWidth="0.9"
          strokeLinecap="round"
          opacity="0.55"
        />
      </svg>
    </span>
  );
}
