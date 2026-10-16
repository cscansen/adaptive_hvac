# Pretty Audio Dashboard — Plan (2026-10-16)

Goal: make `/dashboard-audio` look polished, centred on a big **now-playing hero with the playing source's album
art**, without losing the functional layout shipped in DCA v0.6.0.

## Where things stand
- The dashboard is **generated** by DCA: `custom_components/dynamic_central_audio/dashboard.py` (pure builder, tests in
  `tests/test_dashboard.py`), saved by the `dynamic_central_audio.rebuild_dashboard` action. Hand edits get overwritten.
- Repo `cscansen/dynamic_central_audio` is **public**, and other people's installs use this builder.
- Current layout: whole-house section (Central audio, whole-house party, source Follow Me, a `media-control` per
  source while playing, "Nothing playing" otherwise), then per zone: Speaker, Follow me, Volume (= offset), Include in
  party. A Diagnostics tab holds the reasoning.
- Album art is available: `media_player.central_airplay` and `media_player.living_room_apple_tv` both expose
  `entity_picture` while playing.
- HACS frontend cards **already installed**: card-mod, mini-media-player, maxi-media-player, layout-card,
  auto-entities, kiosk-mode. Using these needs no new supply-chain exposure.
- Volume note: the zone "Volume" slider must stay the offset. DCA re-applies base + offset every 60 s, so a raw
  speaker slider snaps back.

## Step 0 — Reference received 2026-10-16 (screenshot)
u/Vesther, "A little look at the dashboard I've been working on" — their own "customizable dashboard project", not a
named card pack, so there is nothing to install to copy it. The look is mostly **theme + card styling**:
- Warm near-black brown background (~#1c1612), cards a shade lighter, 1px warm hairline borders, ~20px radius.
- **Active tiles glow amber**: gradient fill (dark gold → brown), amber icon; inactive tiles flat and muted.
- Big light-weight clock/headline type; small muted secondary lines; monospace micro-labels (`24 H`, `LOW · HIGH`).
- Media card: album art fills the card, dark gradient at the bottom, title/artist overlaid, round white pause
  button, thin progress bar with times.
- Section headers with a muted count ("Lights 5 on") and pill action buttons ("All off", "Open all").
- Implication for us: route A (installed cards) gets very close — a scoped theme (view-level `theme:`, so the
  rest of HA is unchanged) + card-mod for the glow/gradients + mini-media-player `artwork: full-cover`.

### Original Step 0 note
The reference is https://www.reddit.com/r/homeassistant/s/S7iuQ5cFjc, but Reddit returns 403 to automated fetches.
User to provide **one** of these:
- a screenshot (drop into the session), or
- the post title / an imgur or GitHub link from the post, or
- an old.reddit.com link (may also be blocked).

From it, identify the card stack (likely Mushroom / Bubble Card / button-card + card-mod / a custom theme).

## Step 1 — Decide the dependency route (user decision)
| Option | What it means | Trade-off |
|---|---|---|
| **A. Installed cards only** (recommended start) | card-mod + mini-media-player; Sections + tiles | Nothing new to vet. Close to most "pretty" looks |
| B. Add a card pack | e.g. Mushroom or Bubble Card, whichever the reference uses | Closest match. Needs pre-install vetting, pinned version, user OK |

Whichever is chosen, the public integration must not *require* custom cards. Add a `style` field to
`rebuild_dashboard` (`standard` default = core cards only, `fancy` = uses custom cards). The builder checks
`lovelace_resources` for the cards and falls back to `standard` with a log warning if they're missing.

## Step 2 — Design (mobile first, light + dark)
1. **Now-playing hero** (full width, top):
   - The playing source's album art as a large image over a blurred, darkened copy of the same art.
   - Title / artist / source name, transport controls, and a whole-house "where it's playing" line (chips of the
     zones currently following).
   - Shows only the source that is actually playing (priority order from DCA config if both are).
   - Idle state: a calm placeholder (icon + "Nothing playing"), not an empty box.
   - Route A: mini-media-player `artwork: full-cover` + card-mod for blur and gradient.
2. **Whole-house strip**: compact pill toggles for Central audio, Party mode, and the source Follow Mes. Party mode
   gets an accent colour when on.
3. **Zone cards** (2 per row on phone):
   - Name and status, the Speaker power button, a Volume slider, and Follow me / In party as small icon toggles.
   - An active zone (following) glows in the accent colour. An idle zone is muted.
4. **Diagnostics tab**: unchanged.
5. Colours come from theme variables, never hard-coded, so light and dark both work. Optional matching theme later.

## Step 3 — Prototype without touching the real dashboard
- Hand-build the design on a **scratch dashboard** `dashboard-audio-preview`, saved via websocket from a scratchpad
  script, with no restart. Prototype hero states: AirPlay playing, ATV playing, nothing playing.
- User reviews on phone and desktop, then iterate. Screenshot via Claude in Chrome if available.

## Step 4 — Fold into the builder and ship
- Port the approved layout into `dashboard.py` behind `style: fancy`, keeping `standard` as is.
- Tests: style switch, fallback when cards are missing, hero visibility logic, zone glow conditions.
- Update the README (Dashboard section), `services.yaml` (`style` field) and the changelog. Version **v0.7.0**.
- Deploy needs **one HA restart** (Python change). Batch it with anything else pending. Then call
  `rebuild_dashboard` with `style: fancy`, verify, delete the preview dashboard, and release (tag == HEAD).

## Open questions for the user
1. The reference (Step 0).
2. Route A or B (Step 1).
3. Should `fancy` be this household's default only (passed by the dashboard's Rebuild button), or the integration
   default for everyone? Recommend: household passes `fancy`; integration default stays `standard`.

## Decisions (user, 2026-10-16)
- Route **B — new cards allowed**. Scope: **this house only** (household Rebuild passes `style: fancy`; integration
  default stays `standard`). Theme scope not answered → default: Audio views only (view-level `theme:`).
- Card pick: **custom-cards/button-card v7.0.1** (per-state styles + reusable templates = the amber-glow tiles;
  templates suit a generated builder). Media hero stays mini-media-player (installed). Mushroom/Bubble not needed.
- Vetting 2026-10-16 (button-card v7.0.1): official HACS org repo, maintainer RomRider (long-standing), last
  stable 2025-11-13, active (pushed 2026-09). 0 GitHub advisories, OSV empty, no open security issues. Release asset
  `button-card.js` sha256 `5d6e9c6afca01e8014653fa56bb5d6aa9248d832c34fb944a7f2c36329bc22d1`, 162 KB, no URLs/fetch/
  XHR/WebSocket; one `new Function` = its documented `[[[ JS ]]]` template engine (runs only dashboard-config JS,
  which only admins can edit). Risk: low. Status: **awaiting user OK to install**, pinned v7.0.1.

## Progress (2026-10-16)
- User OK'd install; theme scope = Audio only for now, but **Ember is meant to become the theme/template for other
  dashboards later** (keep templates generic: `ember_base`/`ember_toggle`/`ember_pill`/`ember_heading`).
- button-card **v7.0.1 installed** via HACS ws (`hacs/repository/download`, repo id 146194325); on-host sha256 matches
  the vetted asset; lovelace resource auto-added.
- Theme `themes/ember.yaml` (repo) → `/homeassistant/themes/ember.yaml`, `frontend.reload_themes`. Applied per view.
- Preview **`/dashboard-audio-preview`** created (admin-only, sidebar "Audio Preview") by
  `dashboards/build_audio_preview.py` (re-run: `~/bin/secret-env HA_TOKEN -- python3 dashboards/build_audio_preview.py`).
  Real `/dashboard-audio` untouched. Next: user review on phone + desktop → iterate → Step 4 (port into DCA builder).
- 2026-10-16 iterations: 3 column sections (hero | zones 1-3 | zones 4-6); each zone = one vertical-stack panel
  (card-mod `#root`), plain-text header, controls on `--glow-card-hi`. User: "so much prettier than old".
- Palette → **Silver** (graphite + white/silver glow), user request. All colours now theme vars `--glow-*`
  (`themes/silver.yaml`, `themes/ember.yaml` both define the full set); builder `THEME = "Silver"`.
  Templates renamed `glow_base/glow_toggle/glow_pill/glow_heading`. Port this into DCA in Step 4.
- Silver made more metallic (gunmetal bg, brushed-silver fill); new **Navy** (French navy + gold). Palettes live in
  `themes/build_themes.py` (generates silver/navy/ember.yaml). Preview has one tab per theme (`THEMES` list) for A/B.
- **Glass** theme (user: "more transparency, apple glass"): translucent cards + `--glow-blur` backdrop-filter over a
  silver light-pool `--glow-backdrop`; new vars glow-backdrop/solid/blur/card-shadow (defaults derived for opaque
  themes; dialogs use opaque `--glow-solid`). Preview tabs: Glass | Silver | Navy.
- User picked **Glass** ("oooh i dig that"). Step 4 coded (uncommitted): `dashboard_fancy.py` (templates `dca_*`,
  `--glow-*` with HA-var fallbacks), `build_dashboard(style, theme)`, service fields `style`/`theme`, missing-card
  fallback in `__init__._missing_cards`, 9 new tests (15 pass), README + changelog, manifest 0.7.0. Builder output
  verified on /dashboard-audio-preview (scratch `dca_fancy_preview.py`). Next: deploy + HA restart (ask user) →
  `rebuild_dashboard {style: fancy, theme: Glass}` → delete preview dashboard → commit/tag/push v0.7.0.
- DONE 2026-10-16: deployed, HA restarted, live dashboard == preview, preview deleted, v0.7.0 released (62fbc15).
