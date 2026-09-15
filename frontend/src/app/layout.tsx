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

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${archivo.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
