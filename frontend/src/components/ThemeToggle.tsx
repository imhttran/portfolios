"use client";

// The light/dark switch.
//
// Both labels are rendered and the stylesheet shows one of them, because which
// one applies depends on a theme that the pre-paint script in the layout has
// already resolved: reading it in here would mean the server render and the
// first client render disagree, which is a hydration error. Doing it in CSS
// keeps the switch correct in the first painted frame, and lets it hide itself
// entirely when no theme was ever resolved - which is the scripting-off case,
// where it would have nothing to switch.
//
// The choice is kept in localStorage, so it outlives the tab. The script treats
// a stored value as final and falls back to the system preference otherwise.
export function ThemeToggle() {
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label="Switch between light and dark theme"
      title="Switch between light and dark theme"
      onClick={() => {
        const root = document.documentElement;
        // Anything that isn't light resolves to dark, which matches the styling
        // default, so a missing attribute can't leave the page unstyled.
        const next = root.dataset.theme === "light" ? "dark" : "light";
        root.dataset.theme = next;
        localStorage.setItem("theme", next);
      }}
    >
      <span className="theme-toggle-to-light" aria-hidden="true">
        Light
      </span>
      <span className="theme-toggle-to-dark" aria-hidden="true">
        Dark
      </span>
    </button>
  );
}
