"""Generate the dashboard themes (themes/<name>.yaml). Each palette defines the --glow-* variable set that the
dashboard builders use, plus the standard HA variables mapped onto it, so themes are interchangeable.

Usage: python3 themes/build_themes.py   then copy *.yaml to /homeassistant/themes/ and call frontend.reload_themes.
"""
from pathlib import Path

PALETTES = {
    "Glass": ("frosted translucent glass over soft silver light", {
        "glow-bg": "#0d0f13",
        "glow-backdrop": ("radial-gradient(circle at 12% 18%, rgba(175, 190, 210, 0.30), transparent 42%), "
                          "radial-gradient(circle at 88% 12%, rgba(125, 135, 155, 0.30), transparent 46%), "
                          "radial-gradient(circle at 62% 88%, rgba(205, 210, 220, 0.18), transparent 46%), "
                          "linear-gradient(160deg, #1d2027 0%, #0d0f13 100%)"),
        "glow-card": "rgba(255, 255, 255, 0.06)", "glow-card-hi": "rgba(255, 255, 255, 0.09)",
        "glow-solid": "#1d2026",
        "glow-line": "rgba(255, 255, 255, 0.14)", "glow-line-strong": "rgba(255, 255, 255, 0.24)",
        "glow-accent": "#ffffff",
        "glow-fill": ("linear-gradient(135deg, rgba(255, 255, 255, 0.30) 0%, rgba(220, 228, 238, 0.15) 50%, "
                      "rgba(255, 255, 255, 0.07) 100%)"),
        "glow-border": "rgba(255, 255, 255, 0.45)", "glow-border-strong": "rgba(255, 255, 255, 0.60)",
        "glow-shadow": "inset 0 1px 0 rgba(255, 255, 255, 0.35), 0 0 28px rgba(220, 230, 245, 0.18)",
        "glow-card-shadow": "inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 8px 30px rgba(0, 0, 0, 0.30)",
        "glow-blur": "blur(20px) saturate(160%)",
        "glow-text": "#f7f8fa", "glow-muted": "#b9bfc8", "glow-faint": "#7d838c"}),
    "Silver": ("gunmetal dark, brushed-silver glow on active", {
        "glow-bg": "#1a1c20", "glow-card": "#24272c", "glow-card-hi": "#2e3137",
        "glow-line": "rgba(220, 228, 236, 0.12)", "glow-line-strong": "rgba(220, 228, 236, 0.20)",
        "glow-accent": "#e3e8ee",
        "glow-fill": "linear-gradient(135deg, #8e949c 0%, #60656c 45%, #3d4046 100%)",
        "glow-border": "rgba(225, 232, 240, 0.45)", "glow-border-strong": "rgba(235, 240, 246, 0.60)",
        "glow-shadow": "0 0 26px rgba(200, 215, 230, 0.16)",
        "glow-text": "#f2f4f7", "glow-muted": "#adb3bb", "glow-faint": "#737881"}),
    "Navy": ("French navy, gold accents", {
        "glow-bg": "#0a1428", "glow-card": "#111d36", "glow-card-hi": "#182746",
        "glow-line": "rgba(212, 175, 95, 0.12)", "glow-line-strong": "rgba(212, 175, 95, 0.22)",
        "glow-accent": "#d4af5f",
        "glow-fill": "linear-gradient(135deg, #5a4824 0%, #2c2e3e 55%, #172341 100%)",
        "glow-border": "rgba(212, 175, 95, 0.45)", "glow-border-strong": "rgba(212, 175, 95, 0.60)",
        "glow-shadow": "0 0 28px rgba(212, 175, 95, 0.14)",
        "glow-text": "#f1ece0", "glow-muted": "#9aa6bd", "glow-faint": "#5d6a85"}),
    "Ember": ("warm dark, amber glow on active", {
        "glow-bg": "#17120e", "glow-card": "#211a15", "glow-card-hi": "#2a211a",
        "glow-line": "rgba(255, 214, 160, 0.08)", "glow-line-strong": "rgba(255, 214, 160, 0.12)",
        "glow-accent": "#e8b45a",
        "glow-fill": "linear-gradient(135deg, #6b5228 0%, #47361d 55%, #33271a 100%)",
        "glow-border": "rgba(232, 180, 90, 0.35)", "glow-border-strong": "rgba(232, 180, 90, 0.45)",
        "glow-shadow": "0 0 28px rgba(232, 180, 90, 0.10)",
        "glow-text": "#f3ebe1", "glow-muted": "#a39484", "glow-faint": "#6f6358"}),
}

COMMON = {
    "primary-color": "var(--glow-accent)", "accent-color": "var(--glow-accent)",
    "primary-background-color": "var(--glow-bg)", "lovelace-background": "var(--glow-backdrop)",
    "secondary-background-color": "var(--glow-solid)", "card-background-color": "var(--glow-solid)",
    "ha-card-background": "var(--glow-card)", "ha-card-border-radius": "20px",
    "ha-card-border-color": "var(--glow-line)", "ha-card-border-width": "1px", "ha-card-box-shadow": "none",
    "primary-text-color": "var(--glow-text)", "secondary-text-color": "var(--glow-muted)",
    "disabled-text-color": "var(--glow-faint)", "divider-color": "var(--glow-line)",
    "state-icon-color": "var(--glow-muted)", "state-active-color": "var(--glow-accent)",
    "state-on-color": "var(--glow-accent)", "state-switch-on-color": "var(--glow-accent)",
    "state-media_player-active-color": "var(--glow-accent)", "tile-color": "var(--glow-accent)",
    "app-header-background-color": "var(--glow-bg)", "app-header-text-color": "var(--glow-text)",
    "app-header-selection-bar-color": "var(--glow-accent)", "switch-checked-color": "var(--glow-accent)",
    "slider-color": "var(--glow-accent)", "slider-bar-color": "var(--glow-line-strong)",
    "mdc-theme-primary": "var(--glow-accent)",
}


# Opaque palettes don't need the glass extras; derive them so every theme defines the full --glow-* set.
DEFAULTS = lambda p: {"glow-backdrop": p["glow-bg"], "glow-solid": p["glow-card"], "glow-blur": "none",
                      "glow-card-shadow": "none"}


def render(name, desc, palette):
    lines = [f"# {name} — {desc}. Generated by themes/build_themes.py; edit the palette there.",
             f"{name}:", "  modes:", "    dark:"]
    lines += [f'      {k}: "{v}"' for k, v in {**DEFAULTS(palette), **palette, **COMMON}.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    here = Path(__file__).parent
    for name, (desc, palette) in PALETTES.items():
        (here / f"{name.lower()}.yaml").write_text(render(name, desc, palette))
        print("wrote", name.lower() + ".yaml")
