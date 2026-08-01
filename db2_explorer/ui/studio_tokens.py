"""Studio Precision design tokens — from stitch_exports/04-design-system/theme.json."""

from __future__ import annotations

# Material Design 3 tokens (Studio Precision)
COLORS = {
    "background": "#faf8ff",
    "surface": "#faf8ff",
    "surface_container_lowest": "#ffffff",
    "surface_container_low": "#f2f3ff",
    "surface_container": "#eaedff",
    "surface_container_high": "#e2e7ff",
    "surface_container_highest": "#dae2fd",
    "surface_variant": "#dae2fd",
    "on_surface": "#131b2e",
    "on_surface_variant": "#434655",
    "on_background": "#131b2e",
    "primary": "#004ac6",
    "primary_container": "#2563eb",
    "on_primary": "#ffffff",
    "on_primary_container": "#eeefff",
    "secondary": "#505f76",
    "secondary_container": "#d0e1fb",
    "on_secondary_container": "#54647a",
    "secondary_fixed": "#d3e4fe",
    "on_secondary_fixed": "#0b1c30",
    "tertiary": "#824500",
    "tertiary_fixed": "#ffdcc3",
    "on_tertiary_fixed": "#2f1500",
    "outline": "#737686",
    "outline_variant": "#c3c6d7",
    "error": "#ba1a1a",
    "success": "#059669",
    "success_bg": "#d1fae5",
    "success_text": "#047857",
    "warning": "#d97706",
    "warning_bg": "#fef3c7",
    "warning_text": "#b45309",
    "error_bg": "#fee2e2",
    "error_text": "#991b1b",
}

# Legacy aliases used by backend modules
COLORS["text"] = COLORS["on_surface"]
COLORS["text_muted"] = COLORS["secondary"]
COLORS["border"] = COLORS["outline_variant"]
COLORS["muted"] = COLORS["surface_container_low"]
COLORS["accent"] = COLORS["warning"]
COLORS["destructive"] = COLORS["error"]

FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Fira+Code:wght@400;500;600&"
    "family=Fira+Sans:wght@300;400;500;600;700&"
    "family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
)
