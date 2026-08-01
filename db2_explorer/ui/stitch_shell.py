"""Load stitch_exports HTML and inject Tailwind + token CSS into Streamlit."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

STITCH_ROOT = Path(__file__).resolve().parents[2] / "stitch_exports"
THEME_JSON = STITCH_ROOT / "04-design-system" / "theme.json"

SCREENS = {
    "home": "03-home-db2-migration-studio",
    "object_explorer": "02-object-explorer-db2-migration-studio",
    "row_setup": "01-row-compare-setup-redgate-style",
    "row_workspace": "05-row-compare-workspace-configuration-panel",
    "schema_setup": "06-schema-compare-setup-redgate-style",
    "schema_workspace": "07-schema-compare-updated-table-structure",
}

_HTML_CACHE: dict[str, str] = {}

# Home card navigation — direct Streamlit multipage URLs (iframe-safe).
HOME_GO_PARAMS = (
    "object_explorer",
    "row_compare",
    "schema_compare",
)
HOME_SWITCH_PAGES = (
    "pages/1_Object_Explorer.py",
    "pages/2_Row_Compare.py",
    "pages/3_Schema_Compare.py",
)


def _streamlit_page_url(page_file: str) -> str:
    stem = Path(page_file).stem
    slug = re.sub(r"^\d+_", "", stem)
    return f"/{slug}"


HOME_CARD_URLS = tuple(_streamlit_page_url(p) for p in HOME_SWITCH_PAGES)
OBJECT_EXPLORER_URL = HOME_CARD_URLS[0]
# Legacy query-param hrefs kept for handle_home_navigation().
HOME_CARD_HREFS = tuple(f"?go={p}" for p in HOME_GO_PARAMS)
OE_CHROME_HEIGHT_PX = 92

_ENTER_BUTTON = re.compile(
    r'<button class="flex items-center gap-sm font-label-caps text-label-caps text-primary '
    r'group-hover:translate-x-1 transition-transform duration-200">\s*'
    r"Enter\s*"
    r'<span class="material-symbols-outlined text-\[16px\]">arrow_forward</span>\s*'
    r"</button>",
    re.DOTALL,
)


def _read_html(screen_key: str) -> str:
    if screen_key not in _HTML_CACHE:
        folder = SCREENS[screen_key]
        path = STITCH_ROOT / folder / "index.html"
        if not path.is_file():
            raise FileNotFoundError(f"Missing stitch HTML: {path}")
        _HTML_CACHE[screen_key] = path.read_text(encoding="utf-8")
    return _HTML_CACHE[screen_key]


def _extract_head_inline_style(html: str) -> str:
    match = re.search(r"<style>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_tailwind_config(html: str) -> str:
    match = re.search(
        r'<script id="tailwind-config">(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _between(html: str, start: str, end: str) -> str:
    i = html.find(start)
    if i < 0:
        return ""
    j = html.find(end, i + len(start))
    if j < 0:
        return html[i:]
    return html[i:j]


def _token_fallback_css() -> str:
    """Plain CSS mirror of stitch Tailwind tokens — works when CDN misses dynamic DOM."""
    if not THEME_JSON.is_file():
        return ""
    theme = json.loads(THEME_JSON.read_text(encoding="utf-8"))
    colors = theme.get("namedColors", {})
    spacing = theme.get("spacing", {})
    typography = theme.get("typography", {})

    lines = [
        ".stitch-ui, .stitch-ui .stApp, .stApp { font-family: 'Fira Sans', sans-serif; }",
        ".material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; vertical-align: middle; }",
    ]
    for name, value in colors.items():
        token = name.replace("_", "-")
        lines.append(f".bg-{token} {{ background-color: {value} !important; }}")
        lines.append(f".text-{token} {{ color: {value} !important; }}")
        lines.append(f".border-{token} {{ border-color: {value} !important; }}")
    for name, value in spacing.items():
        lines.append(f".p-{name} {{ padding: {value} !important; }}")
        lines.append(f".px-{name} {{ padding-left: {value} !important; padding-right: {value} !important; }}")
        lines.append(f".py-{name} {{ padding-top: {value} !important; padding-bottom: {value} !important; }}")
        lines.append(f".m-{name} {{ margin: {value} !important; }}")
        lines.append(f".mb-{name} {{ margin-bottom: {value} !important; }}")
        lines.append(f".mt-{name} {{ margin-top: {value} !important; }}")
        lines.append(f".gap-{name} {{ gap: {value} !important; }}")
    for name, spec in typography.items():
        ff = spec.get("fontFamily", "Fira Sans")
        fs = spec.get("fontSize", "14px")
        fw = spec.get("fontWeight", "400")
        lh = spec.get("lineHeight", "20px")
        ls = spec.get("letterSpacing", "normal")
        lines.append(
            f".font-{name} {{ font-family: '{ff}', sans-serif !important; "
            f"font-size: {fs} !important; font-weight: {fw} !important; "
            f"line-height: {lh} !important; letter-spacing: {ls} !important; }}"
        )
        lines.append(
            f".text-{name} {{ font-family: '{ff}', sans-serif !important; "
            f"font-size: {fs} !important; font-weight: {fw} !important; "
            f"line-height: {lh} !important; letter-spacing: {ls} !important; }}"
        )
    lines.extend(
        [
            ".hero-panel { background:#fff;border:1px solid #e2e8f0;box-shadow:0 1px 2px rgba(0,0,0,.05);border-radius:4px; }",
            ".rounded-DEFAULT, .rounded { border-radius: 4px !important; }",
            ".rounded-lg { border-radius: 8px !important; }",
            ".rounded-xl { border-radius: 12px !important; }",
            ".rounded-full { border-radius: 9999px !important; }",
            ".uppercase { text-transform: uppercase !important; }",
            ".font-bold { font-weight: 700 !important; }",
            ".font-semibold { font-weight: 600 !important; }",
            ".font-medium { font-weight: 500 !important; }",
            ".tracking-wider { letter-spacing: 0.05em !important; }",
            ".tracking-tight { letter-spacing: -0.02em !important; }",
            ".border-b { border-bottom-width: 1px !important; border-bottom-style: solid !important; }",
            ".border-b-2 { border-bottom-width: 2px !important; border-bottom-style: solid !important; }",
            ".border { border-width: 1px !important; border-style: solid !important; }",
            ".sticky { position: sticky !important; }",
            ".top-0 { top: 0 !important; }",
            ".z-50 { z-index: 50 !important; }",
            ".z-40 { z-index: 40 !important; }",
            ".flex { display: flex !important; }",
            ".inline-block { display: inline-block !important; }",
            ".grid { display: grid !important; }",
            ".hidden { display: none !important; }",
            ".flex-col { flex-direction: column !important; }",
            ".flex-wrap { flex-wrap: wrap !important; }",
            ".flex-1 { flex: 1 1 0% !important; }",
            ".flex-grow { flex-grow: 1 !important; }",
            ".items-center { align-items: center !important; }",
            ".justify-between { justify-content: space-between !important; }",
            ".justify-center { justify-content: center !important; }",
            ".text-center { text-align: center !important; }",
            ".w-full { width: 100% !important; }",
            ".h-12 { height: 3rem !important; }",
            ".h-10 { height: 2.5rem !important; }",
            ".min-h-screen { min-height: 100vh !important; }",
            ".max-w-3xl { max-width: 48rem !important; }",
            ".max-w-6xl { max-width: 72rem !important; }",
            ".mx-auto { margin-left: auto !important; margin-right: auto !important; }",
            ".no-underline { text-decoration: none !important; }",
            ".group:hover .group-hover\\:translate-x-1 { transform: translateX(0.25rem); }",
            ".transition-colors { transition: color 0.15s, background-color 0.15s !important; }",
            ".transition-all { transition: all 0.3s !important; }",
            ".hover\\:border-primary:hover { border-color: #004ac6 !important; }",
            ".grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)) !important; }",
            ".grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }",
            ".grid-cols-5 { grid-template-columns: repeat(5, minmax(0, 1fr)) !important; }",
            "@media (min-width: 768px) { .md\\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; } .md\\:flex { display: flex !important; } }",
            ".custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }",
            ".custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }",
        ]
    )
    return "\n".join(lines)


def bootstrap_stitch() -> None:
    """Inject Tailwind CDN, stitch tokens, and fallback CSS into the parent document."""
    home_html = _read_html("home")
    oe_html = _read_html("object_explorer")
    tw_config = _extract_tailwind_config(home_html)
    inline_style = _extract_head_inline_style(home_html) + "\n" + _extract_head_inline_style(oe_html)
    fallback = _token_fallback_css()

    cfg_js = json.dumps(tw_config)
    style_js = json.dumps(inline_style + "\n" + fallback)

    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const root = doc.documentElement;
          root.classList.add("stitch-ui", "light");

          if (!doc.getElementById("stitch-inline-styles")) {{
            const style = doc.createElement("style");
            style.id = "stitch-inline-styles";
            style.textContent = {style_js};
            doc.head.appendChild(style);
          }}

          if (!doc.getElementById("stitch-fonts")) {{
            const fonts = [
              "https://fonts.googleapis.com/css2?family=Fira+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Fira+Code:wght@400;500&display=swap",
              "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
            ];
            fonts.forEach((href) => {{
              const link = doc.createElement("link");
              link.rel = "stylesheet";
              link.href = href;
              doc.head.appendChild(link);
            }});
            const marker = doc.createElement("meta");
            marker.id = "stitch-fonts";
            doc.head.appendChild(marker);
          }}

          if (!doc.getElementById("stitch-tailwind-config")) {{
            const cfg = doc.createElement("script");
            cfg.id = "stitch-tailwind-config";
            cfg.textContent = {cfg_js};
            doc.head.appendChild(cfg);
          }}

          function refreshTailwind() {{
            const tw = window.parent.tailwind;
            if (tw && typeof tw.refresh === "function") {{
              tw.refresh();
            }}
          }}

          if (!doc.getElementById("stitch-tailwind-cdn")) {{
            const tw = doc.createElement("script");
            tw.id = "stitch-tailwind-cdn";
            tw.src = "https://cdn.tailwindcss.com?plugins=forms,container-queries";
            tw.onload = function () {{
              refreshTailwind();
              let timer = null;
              const app = doc.querySelector(".stApp");
              if (app && window.parent.MutationObserver) {{
                new window.parent.MutationObserver(function () {{
                  if (timer) window.parent.clearTimeout(timer);
                  timer = window.parent.setTimeout(refreshTailwind, 80);
                }}).observe(app, {{ childList: true, subtree: true, attributes: true }});
              }}
            }};
            doc.head.appendChild(tw);
          }} else {{
            refreshTailwind();
          }}
        }})();
        </script>
        """,
        height=1,
    )


def render_html(fragment: str) -> None:
    text = fragment.strip()
    if text:
        st.html(text)


def _extract_document_head(html: str) -> str:
    match = re.search(r"<head>(.*?)</head>", html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def inject_shell_component(*, tailwind_config_source: str = "home") -> None:
    """Zero-height iframe that injects Tailwind + spacing reset into the parent document."""
    css = (
        streamlit_chrome_css()
        + home_iframe_css()
        + home_reset_css()
        + oe_workspace_css()
    )
    css_js = json.dumps(css)
    tw_config = _extract_tailwind_config(_read_html(tailwind_config_source))
    cfg_js = json.dumps(tw_config)
    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          doc.documentElement.classList.add("stitch-shell", "light");
          if (!doc.getElementById("stitch-shell-reset")) {{
            const s = doc.createElement("style");
            s.id = "stitch-shell-reset";
            s.textContent = {css_js};
            doc.head.appendChild(s);
          }}
          if (!doc.getElementById("stitch-tailwind-config")) {{
            const c = doc.createElement("script");
            c.id = "stitch-tailwind-config";
            c.textContent = {cfg_js};
            doc.head.appendChild(c);
          }}
          if (!doc.getElementById("stitch-tailwind-cdn")) {{
            const t = doc.createElement("script");
            t.id = "stitch-tailwind-cdn";
            t.src = "https://cdn.tailwindcss.com?plugins=forms,container-queries";
            t.onload = function () {{
              if (window.parent.tailwind && window.parent.tailwind.refresh) {{
                window.parent.tailwind.refresh();
              }}
            }};
            doc.head.appendChild(t);
          }}
          if (!doc.getElementById("stitch-nav-bridge")) {{
            const n = doc.createElement("script");
            n.id = "stitch-nav-bridge";
            n.textContent = `
              (function () {{
                if (window.__stitchNavListener) return;
                window.__stitchNavListener = true;
                window.addEventListener("message", function (ev) {{
                  if (!ev.data) return;
                  if (ev.data.type === "stitch-nav" && ev.data.href) {{
                    const href = ev.data.href;
                    const path = window.location.pathname || "/";
                    window.location.assign(path + (href.charAt(0) === "?" ? href : href));
                    return;
                  }}
                  if (ev.data.type === "stitch-oe-nav" && ev.data.url) {{
                    window.location.assign(ev.data.url);
                  }}
                }});
              }})();
            `;
            doc.head.appendChild(n);
          }}
        }})();
        </script>
        """,
        height=0,
    )


def handle_home_navigation() -> None:
    """Redirect ?go= query param to the matching Streamlit page."""
    go = st.query_params.get("go", "")
    routes = dict(zip(HOME_GO_PARAMS, HOME_SWITCH_PAGES))
    target = routes.get(go)
    if target:
        st.query_params.clear()
        st.switch_page(target)


def _wire_home_page(html: str) -> str:
    """Prepare stitch home body HTML with query-param card links."""
    card_markers = [
        ("<!-- Card 1: Object Explorer -->", "<!-- Card 2: Row Compare -->", HOME_CARD_URLS[0]),
        ("<!-- Card 2: Row Compare -->", "<!-- Card 3: Schema Compare -->", HOME_CARD_URLS[1]),
        ("<!-- Card 3: Schema Compare -->", "</div>\n<!-- Decorative UI Element", HOME_CARD_URLS[2]),
    ]
    for start, end, href in card_markers:
        raw = _between(html, start, end)
        card = raw.replace(start, "").strip()
        card = _ENTER_BUTTON.sub(
            (
                '<span class="flex items-center gap-sm font-label-caps text-label-caps text-primary '
                'group-hover:translate-x-1 transition-transform duration-200">'
                'Enter <span class="material-symbols-outlined text-[16px]">arrow_forward</span></span>'
            ),
            card,
            count=1,
        )
        card = re.sub(
            r'^<div class="group ',
            f'<a href="{href}" class="stitch-card-link no-underline text-inherit cursor-pointer group ',
            card,
            count=1,
        )
        close_idx = card.rfind("</div>")
        if close_idx >= 0:
            card = card[:close_idx] + "</a>" + card[close_idx + len("</div>") :]
        html = html.replace(raw, start + "\n" + card + "\n", 1)

    nav = "<nav " + _between(html, "<nav ", "</nav>") + "</nav>"
    main = "<main " + _between(html, "<main ", "</main>") + "</main>"
    foot = "<footer " + _between(html, "<footer ", "</footer>") + "</footer>"
    return (
        '<div class="stitch-home-body bg-surface-container-lowest text-on-surface '
        'min-h-screen flex flex-col">'
        f"{nav}{main}{foot}</div>"
    )


def render_home_screen() -> None:
    """Render stitch home HTML in the Streamlit document (not a sandboxed iframe)."""
    inject_shell_component(tailwind_config_source="home")
    body = _wire_home_page(_read_html("home"))
    st.html(body)


def home_reset_css() -> str:
    """Zero out every Streamlit layout wrapper on stitch shell pages."""
    return """
    html.stitch-shell, html.stitch-shell body, html.stitch-shell #root {
        margin: 0 !important;
        padding: 0 !important;
        overflow-x: hidden !important;
    }
    html.stitch-shell .stApp {
        margin: 0 !important;
        padding: 0 !important;
        background: #faf8ff !important;
    }
    html.stitch-shell header[data-testid="stHeader"],
    html.stitch-shell footer,
    html.stitch-shell section[data-testid="stSidebar"],
    html.stitch-shell [data-testid="collapsedControl"],
    html.stitch-shell [data-testid="stToolbar"],
    html.stitch-shell [data-testid="stStatusWidget"],
    html.stitch-shell [data-testid="stDecoration"],
    html.stitch-shell [data-testid="stAppDeployButton"],
    html.stitch-shell [data-testid="stHeaderActionElements"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: hidden !important;
        visibility: hidden !important;
        pointer-events: none !important;
        border: none !important;
    }
    html.stitch-shell [data-testid="stAppViewContainer"],
    html.stitch-shell [data-testid="stAppViewContainer"] > section,
    html.stitch-shell [data-testid="stMain"],
    html.stitch-shell [data-testid="stMainBlockContainer"],
    html.stitch-shell .main,
    html.stitch-shell .block-container,
    html.stitch-shell [data-testid="stVerticalBlock"],
    html.stitch-shell [data-testid="stVerticalBlockBorderWrapper"],
    html.stitch-shell [data-testid="stElementContainer"],
    html.stitch-shell .element-container,
    html.stitch-shell [data-testid="stMarkdownContainer"],
    html.stitch-shell [data-testid="stMarkdown"] {
        padding: 0 !important;
        margin: 0 !important;
        max-width: none !important;
        gap: 0 !important;
    }
    html.stitch-shell [data-testid="stVerticalBlock"] > div {
        padding: 0 !important;
        margin: 0 !important;
        gap: 0 !important;
    }
    html.stitch-shell [data-testid="stIFrame"],
    html.stitch-shell [data-testid="stCustomComponentV1"],
    html.stitch-shell .stCustomComponentV1 {
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    html.stitch-shell iframe {
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
        width: 100vw !important;
        max-width: 100vw !important;
        min-height: 100vh !important;
        vertical-align: top !important;
        pointer-events: auto !important;
    }
    html.stitch-shell .stitch-card-link { cursor: pointer !important; }
    html.stitch-shell .stitch-card-link:hover { text-decoration: none !important; }
    html.stitch-shell iframe[height="0"],
    html.stitch-shell iframe[height="1"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    """


def _nav_replace(html: str, active: str) -> str:
    links = [
        ("home", "Home"),
        ("projects", "Projects"),
        ("migrations", "Migrations"),
        ("monitoring", "Monitoring"),
        ("settings", "Settings"),
    ]
    for key, label in links:
        active_cls = 'class="text-primary font-bold border-b-2 border-primary pb-1 font-body-md text-body-md"'
        idle_cls = (
            'class="text-secondary hover:bg-surface-container-high transition-colors '
            'font-body-md text-body-md px-sm py-xs rounded"'
        )
        replacement = f"<span {active_cls}>{label}</span>" if key == active else f"<span {idle_cls}>{label}</span>"
        html = re.sub(
            rf'<a class="[^"]*" href="#">{re.escape(label)}</a>',
            replacement,
            html,
            count=1,
        )
    return html


def home_nav(active: str = "home") -> None:
    html = _read_html("home")
    nav = _between(html, "<nav ", "</nav>")
    nav = "<nav " + nav + "</nav>"
    render_html(_nav_replace(nav, active))


def home_shell() -> None:
    html = _read_html("home")
    hero = _between(html, "<!-- Hero Section -->", "<!-- Centered Card Grid -->")
    hero = hero.replace("<!-- Hero Section -->", "").strip()
    render_html(
        '<main class="flex-grow flex flex-col items-center px-margin-edge py-xl">'
        + hero
        + "</main>"
    )


def home_card_html(card_index: int) -> str:
    html = _read_html("home")
    markers = [
        ("<!-- Card 1: Object Explorer -->", "<!-- Card 2: Row Compare -->"),
        ("<!-- Card 2: Row Compare -->", "<!-- Card 3: Schema Compare -->"),
        ("<!-- Card 3: Schema Compare -->", "</div>\n<!-- Decorative"),
    ]
    start, end = markers[card_index]
    return _between(html, start, end).replace(start, "").strip()


def home_footer_html() -> str:
    html = _read_html("home")
    return _between(html, "<!-- Footer -->", "<!-- Micro-interaction Script -->").replace(
        "<!-- Footer -->", ""
    ).strip()


def _wire_oe_chrome(source: str, *, db_count: int) -> str:
    """Build nav + sub-toolbar from stitch 02-object-explorer index.html."""
    chrome = _between(source, "<nav ", "<!-- Main Workspace -->").strip()
    if not chrome.startswith("<nav"):
        chrome = "<nav " + chrome

    chrome = re.sub(
        r'<button[^>]*>\s*'
        r'<span class="material-symbols-outlined text-sm">arrow_back</span>\s*Home\s*</button>',
        (
            '<a href="/?oe_clear=1" id="oe-home-back" '
            'class="oe-home-link flex items-center gap-1 text-on-secondary-container hover:text-primary '
            'transition-colors text-sm font-medium no-underline">'
            '<span class="material-symbols-outlined text-sm">arrow_back</span> Home</a>'
        ),
        chrome,
        count=1,
        flags=re.DOTALL,
    )

    db_label = f"{db_count} Database{'s' if db_count != 1 else ''} Configured"
    chrome = re.sub(r"\d+ Databases Configured", db_label, chrome)

    head = _extract_document_head(source)
    shell_script = ""  # shell injected by inject_shell_component on the OE page
    frame_script = f"""
<script>
(function () {{
  function syncFrameHeight() {{
    window.parent.postMessage(
      {{ type: "streamlit:setFrameHeight", height: {OE_CHROME_HEIGHT_PX} }},
      "*"
    );
  }}
  syncFrameHeight();
  window.addEventListener("load", syncFrameHeight);
  window.addEventListener("resize", syncFrameHeight);
}})();
</script>
"""
    return (
        "<!DOCTYPE html><html class='light' lang='en'>"
        f"<head>{head}{shell_script}</head>"
        f"<body class='font-body-md text-body-md m-0 overflow-hidden flex flex-col bg-surface-container-lowest'>"
        f"{chrome}{frame_script}</body></html>"
    )


def render_oe_chrome(*, db_count: int = 0) -> None:
    """Render stitch 02-object-explorer nav + sub-toolbar directly."""
    inject_shell_component(tailwind_config_source="object_explorer")
    html = _wire_oe_chrome(_read_html("object_explorer"), db_count=db_count)
    components.html(html, height=OE_CHROME_HEIGHT_PX, scrolling=False)


def oe_chrome(*, db_count: int = 0) -> None:
    """Alias — renders stitch object-explorer chrome iframe."""
    render_oe_chrome(db_count=db_count)


def oe_panel_open(title: str, *, icon: str = "", uppercase: bool = True) -> None:
    uc = " uppercase" if uppercase else ""
    icon_html = (
        f'<span class="material-symbols-outlined text-outline text-lg">{icon}</span>'
        if icon
        else ""
    )
    render_html(
        f'<section class="hero-panel p-md flex flex-col gap-md mb-md">'
        f'<div class="flex items-center justify-between">'
        f'<h3 class="font-label-caps text-label-caps text-primary{uc}">{title}</h3>'
        f"{icon_html}</div>"
    )


def oe_panel_close() -> None:
    render_html("</section>")


def fleet_panel_header_html(*, db_count: int) -> str:
    label = f"{db_count} database{'s' if db_count != 1 else ''}"
    return (
        '<div class="p-md border-b border-outline-variant bg-surface-container-low '
        'flex items-center justify-between">'
        f'<h3 class="font-label-caps text-label-caps text-on-surface m-0">'
        f"Database Fleet ({label})</h3></div>"
    )


def workspace_nav(active: str, *, page_title: str, page_subtitle: str = "") -> None:
    """Top nav from row/schema workspace stitch screens."""
    html = _read_html("row_workspace")
    header = _between(html, "<!-- TopNavBar -->", "</header>")
    header = header.replace("<!-- TopNavBar -->", "").strip()
    if not header.startswith("<header"):
        header = "<header " + header
    header = header + "</header>"
    header = _nav_replace(header.replace("<nav ", "<nav ").replace("</nav>", "</nav>"), active)
    if page_title:
        header = re.sub(
            r"<span class=\"font-headline-md[^\"]*\">DB2 Migration Studio</span>",
            f'<span class="font-headline-md text-headline-md font-bold text-on-surface">DB2 Migration Studio</span>'
            f'<div class="h-4 w-[1px] bg-outline-variant mx-sm"></div>'
            f'<div class="flex flex-col">'
            f'<span class="font-title-sm text-primary font-bold">{page_title}</span>'
            f'<span class="text-[10px] leading-tight text-secondary uppercase tracking-wider">{page_subtitle}</span>'
            f"</div>",
            header,
            count=1,
        )
    render_html(header)


def row_toolbar_html() -> str:
    html = _read_html("row_workspace")
    return _between(html, "</header>", "<main ").replace("</header>", "").strip()


def row_setup_header_html() -> str:
    html = _read_html("row_setup")
    chunk = _between(html, "<!-- Modal Header -->", "<!-- Two-Column Connection Fields -->")
    return chunk.replace("<!-- Modal Header -->", "").strip()


def row_setup_source_header_html() -> str:
    html = _read_html("row_setup")
    chunk = _between(html, "<!-- Left Column (Source) -->", "<div class=\"space-y-md\">")
    inner = re.search(
        r'<div class="flex items-center gap-sm mb-lg">.*?</div>\s*</div>',
        chunk,
        re.DOTALL,
    )
    return inner.group(0) if inner else ""


def row_setup_target_header_html() -> str:
    html = _read_html("row_setup")
    chunk = _between(html, "<!-- Right Column (Target) -->", "<div class=\"space-y-md\">")
    inner = re.search(
        r'<div class="flex items-center gap-sm mb-lg">.*?</div>\s*</div>',
        chunk,
        re.DOTALL,
    )
    return inner.group(0) if inner else (
        '<div class="flex items-center gap-sm mb-lg">'
        '<div class="w-10 h-10 bg-surface-container flex items-center justify-center rounded">'
        '<span class="material-symbols-outlined text-tertiary">cloud</span></div>'
        '<div><h3 class="font-title-sm text-title-sm text-on-surface">AZURE SQL TARGET</h3>'
        '<p class="font-label-caps text-label-caps text-secondary uppercase">Production Instance</p>'
        "</div></div>"
    )


def schema_setup_header_html() -> str:
    html = _read_html("schema_setup")
    chunk = _between(html, "<!-- Modal Header -->", "<!-- Two-Column Connection Fields -->")
    return chunk.replace("<!-- Modal Header -->", "").strip()


def schema_setup_gitlab_header_html() -> str:
    html = _read_html("schema_setup")
    chunk = _between(html, "<!-- Left: GitLab Source -->", "<div class=\"space-y-md\">")
    inner = re.search(r"<div class=\"flex items-center gap-sm mb-lg\">.*?</div>\s*</div>", chunk, re.DOTALL)
    return inner.group(0) if inner else ""


def schema_setup_target_header_html() -> str:
    html = _read_html("schema_setup")
    chunk = _between(html, "<!-- Right: Azure SQL Target -->", "<div class=\"space-y-md\">")
    inner = re.search(
        r'<div class="flex items-center gap-sm mb-lg">.*?</div>\s*</div>',
        chunk,
        re.DOTALL,
    )
    return inner.group(0) if inner else ""


def streamlit_chrome_css() -> str:
    return """
    header[data-testid="stHeader"], footer, section[data-testid="stSidebar"],
    [data-testid="collapsedControl"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: none !important; }
    .stApp { background: #faf8ff !important; font-family: 'Fira Sans', sans-serif !important; }
    [data-testid="stAppViewContainer"] > section { padding-top: 0 !important; }
    .stApp .stTextInput input, .stApp .stNumberInput input,
    .stApp textarea, .stApp [data-baseweb="select"] > div {
        border: 1px solid #c3c6d7 !important;
        border-radius: 4px !important;
        background: #faf8ff !important;
        font-size: 0.875rem !important;
        font-family: 'Fira Sans', sans-serif !important;
    }
    .stApp .stTextInput input:focus, .stApp textarea:focus {
        border-color: #004ac6 !important;
        box-shadow: 0 0 0 1px #004ac6 !important;
    }
    .stButton > button[kind="primary"] {
        background: #004ac6 !important;
        color: #fff !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        border: none !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #c3c6d7 !important;
        border-radius: 4px !important;
        background: #ffffff !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    }
    .stApp .stPageLink a {
        color: #004ac6 !important;
        font-size: 0.6875rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        text-decoration: none !important;
    }
    iframe[height="1"] { position: absolute !important; width: 0 !important; height: 0 !important; border: 0 !important; }
    """

def oe_workspace_css() -> str:
    """Workspace area below the object-explorer chrome iframe."""
    return """
    html.stitch-shell [data-testid="stVerticalBlock"] { gap: 0 !important; }
    html.stitch-shell [data-testid="stElementContainer"] { margin: 0 !important; }
    html.stitch-shell .stitch-oe-workspace {
        padding: 16px !important;
        background: #faf8ff !important;
        min-height: calc(100vh - 92px) !important;
    }
    html.stitch-shell iframe[height="92"] {
        display: block !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        width: 100vw !important;
        max-width: 100vw !important;
        min-height: 0 !important;
        vertical-align: top !important;
    }
    """


def home_iframe_css() -> str:
    """Full-bleed stitch page iframe."""
    return """
    html.stitch-shell .block-container { padding: 0 !important; max-width: none !important; }
    html.stitch-shell [data-testid="stAppViewContainer"] > section { padding: 0 !important; }
    html.stitch-shell [data-testid="stMainBlockContainer"] { padding: 0 !important; }
    """


def shell_iframe_css() -> str:
    """CSS for a single full-viewport stitch iframe page."""
    return (
        home_iframe_css()
        + home_reset_css()
        + """
    html.stitch-shell [data-testid="stVerticalBlock"] { gap: 0 !important; padding: 0 !important; }
    html.stitch-shell [data-testid="stElementContainer"] { margin: 0 !important; padding: 0 !important; }
    html.stitch-shell [data-testid="stMarkdownContainer"] { margin: 0 !important; padding: 0 !important; }
    html.stitch-shell iframe {
        display: block !important;
        width: 100vw !important;
        max-width: 100vw !important;
        min-height: 100vh !important;
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        vertical-align: top !important;
        pointer-events: auto !important;
    }
    html.stitch-shell iframe[height="0"] {
        position: fixed !important;
        width: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    """
    )
