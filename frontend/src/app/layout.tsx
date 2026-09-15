import type { Metadata } from "next";
import { Archivo, Great_Vibes, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { SITE } from "@/lib/site";

// Two faces, three jobs: Archivo carries the display and body text, and Plex
// Mono is reserved for the technical layer - frame numbers, metadata, the footer
// - which is where a proof sheet keeps its facts. The signature is the third:
// a script, only ever used to sign work, so it never competes with the body.
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

const greatVibes = Great_Vibes({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-script",
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
// It always writes data-theme, even when nothing is stored, and the value it
// writes when nothing is stored is light - the site's own look, which is what a
// first-time visitor gets in either theme and what a visitor with scripting off
// gets too. The attribute is also what tells the switch it has something to
// switch.
//
// data-theme-chosen is the narrower fact, and the only thing an artist's theme
// defers to: it is written only when somebody actually picked, never when the
// value merely fell out of the system preference. Without that distinction an
// artist's page could not tell "I chose light" from "light happened to me",
// and would have to override the one that was asked for.
const THEME_SCRIPT = `
(function () {
  var stored = null;
  try {
    stored = localStorage.getItem("theme");
  } catch {
    /* Storage can be blocked; the site still has to pick a look. */
  }
  var chosen = stored === "light" || stored === "dark";
  if (!chosen) {
    /* Light is the site's own look, so that is the default rather than the
       system preference: a dark-system visitor would otherwise land on a page
       nothing like the one they asked for. */
    stored = "light";
  }
  document.documentElement.dataset.theme = stored;
  if (chosen) {
    document.documentElement.dataset.themeChosen = "";
  }
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${plexMono.variable} ${greatVibes.variable}`}
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
