# Shareit — UI / Visual Design Notes

Direction: **modern, premium, minimal — "clean, straight to business."** Inspired by two
references (a soft minimal file dashboard; the "Symmetric" storage dashboard). We borrow the
*aesthetic* (color, type, spacing, rounded surfaces, mono numbers), not their features
(folders, tags, search, sharing are multi-user roadmap).

## Principles
- Minimal and airy: generous whitespace, few borders, soft rounded surfaces.
- One calm brand accent (mint); primary actions use it; everything else is neutral.
- Consistency over decoration — everything is driven by design tokens.
- Light **and** dark themes, with a toggle; default to the OS setting.

## Color tokens (CSS variables in app/static/styles.css)
Accent (both themes): **mint**
- `--accent` ≈ #1FC9A3, `--accent-strong` (hover) ≈ #15B894
- `--accent-contrast` (text on accent) ≈ near-black #052B21
- `--accent-soft` = pale mint surface (light) / translucent mint (dark)

Light: `--bg` #F7F8F9 · `--surface` #FFF · `--surface-2` #F1F3F5 · `--border` #E6E8EB ·
`--fg` #1A1D21 · `--muted` #6B7280
Dark:  `--bg` #0E1012 · `--surface` #16191D · `--surface-2` #1E2227 · `--border` #262A31 ·
`--fg` #E6E8EB · `--muted` #9AA3AD

## Typography
- UI: **Inter** (400/500/600/700) via Google Fonts. Base ~15px.
- Data (file sizes, dates, numbers): **IBM Plex Mono** — reads precise/premium (ref 2).

## Shape, spacing, motion
- Radii: ~14px cards/inputs, ~10px small, pill for chips. Soft shadows in light, borders in dark.
- Spacing rhythm: 4/8/12/16/24/32. Transitions ~150ms on interactive states; focus-visible ring in accent.

## Layout (current pages, re-skinned — no new features)
- **Header:** "Shareit" wordmark left; theme toggle + Log out right.
- **Top bar:** two equal labeled panels — "Share clipboard between devices" and "Upload a file"
  (clipboard preview one-liner + Copy icon + Share; custom Browse control + filename + Upload + progress).
- **Storage bar:** slim track + mint fill, "used of capacity" in mono.
- **File list:** table on desktop (Name w/ type icon, Type, Size, Uploaded, kebab), sortable with
  arrow + highlight; stacks into cards on mobile. Sizes/dates in mono.
- **Login:** centered card (surface + shadow), wordmark + password + button.

## Theme behavior
- Early inline script sets `data-theme` from localStorage before paint (no flash).
- CSS: `:root` = light; `:root[data-theme="dark"]` = dark; `@media (prefers-color-scheme: dark)`
  applies dark when the user hasn't chosen (`:root:not([data-theme="light"])`).
- Toggle button flips + persists the choice.

## Iteration log
- (to fill in as we refine: component tweaks, color adjustments, etc.)
