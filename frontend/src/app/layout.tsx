import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { SITE } from "@/lib/site";

// Two faces, three jobs: Archivo carries the display and body text, and Plex
// Mono is reserved for the technical layer - frame numbers, metadata, the
// footer - which is where a proof sheet keeps its facts.
const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

// Only the description lives here: every page renders its own <PageTitle>, so
// setting a title at the layout level would override all of them.
export const metadata: Metadata = {
  description: SITE.statement,
};

// The theme, settled before the first paint.
//
// A plain inline <script> rather than next/script: with a beforeInteractive
// strategy Next pushes the source onto a queue that the framework drains once
// it has booted, which is after the first paint and therefore too late. An
// inline script at the top of the body is parsed and run before the content
// below it is, which is what keeps the page from painting one theme and then
// the other.
//
// It always writes data-theme, even when nothing is stored. For a first-time
// visitor the value it writes is the one color-scheme already resolved from the
// system, so no repaint happens - while the attribute is also what tells the
// switch it has something to switch, and a visitor with scripting off never
// gets it and so never sees the switch.
const THEME_SCRIPT = `
(function () {
  var stored = null;
  try {
    stored = localStorage.getItem("theme");
  } catch {
    /* Storage can be blocked; the system preference still applies. */
  }
  if (stored !== "light" && stored !== "dark") {
    stored = window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }
  document.documentElement.dataset.theme = stored;
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${plexMono.variable}`}
      // The script below sets data-theme here before React hydrates, so the
      // server's markup and the client's differ by exactly that attribute.
      suppressHydrationWarning
    >
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}
