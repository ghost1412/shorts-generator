"""The look of the browser app: CSS only (no logic), kept apart from the layout code in webui.py.

* The "What do you want to make?" chooser becomes a grid of icon cards, each with a one-line description. The icons are inline SVG
  masks (nothing is fetched from the internet), and they take the text colour, so they work in light and dark mode.
* A branded header, softer cards, a primary button that stays in view while a long form scrolls, and a clearer progress card.
"""

ICON_STYLE = "fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'"

# label shown in the chooser -> (svg body, one-line description)
MODES = [
    ("Shorts", "<rect x='7' y='2' width='10' height='20' rx='2'/><path d='M12 18h.01'/>", "Tall clips from a long video"),
    ("Highlights video", "<rect x='2' y='4' width='20' height='16' rx='2'/><path d='M7 4v16M17 4v16M2 12h20M2 8h5M2 16h5M17 8h5M17 16h5'/>",
     "One long best-of video"),
    ("Dub into another language", "<circle cx='12' cy='12' r='10'/><path d='M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20'/>",
     "A new voice and subtitles"),
    ("Recap (trip, wedding, event)", "<path d='M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z'/><circle cx='12' cy='10' r='3'/>",
     "Many videos into one story"),
    ("Photo reel", "<rect x='3' y='3' width='18' height='18' rx='2'/><circle cx='9' cy='9' r='2'/><path d='M21 15l-5-5L5 21'/>",
     "Photos into a moving reel"),
    ("Video from an idea", "<path d='M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z'/>", "Start from a topic"),
    ("Clip tool (all options)", "<circle cx='6' cy='6' r='3'/><circle cx='6' cy='18' r='3'/><path d='M20 4L8.12 15.88M14.47 14.48L20 20M8.12 8.12L12 12'/>",
     "Every setting, one screen"),
]


def mode_card_css():
    """CSS for the mode chooser (the radio with elem_id sf-modes): one icon and one description per option."""
    css = [
        "#sf-modes .wrap { display: grid !important; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }",
        "#sf-modes label { display: flex !important; flex-direction: column; align-items: flex-start; gap: 2px; min-height: 104px; "
        "padding: 14px 16px !important; border-radius: 14px !important; border: 1px solid rgba(128,128,128,.30) !important; "
        "background: rgba(128,128,128,.07) !important; cursor: pointer; position: relative; transition: border-color .15s, background .15s, transform .15s; }",
        "#sf-modes label:hover { border-color: #ea580c !important; transform: translateY(-1px); }",
        "#sf-modes label input { display: block !important; position: absolute; opacity: 0; width: 1px; height: 1px; pointer-events: none; }",
        "#sf-modes label:focus-within { outline: 2px solid #ea580c; outline-offset: 2px; }",
        "#sf-modes label, #sf-modes label span, #sf-modes label.selected span { color: var(--body-text-color) !important; }",
        "#sf-modes label span { margin: 0 !important; padding: 0 !important; }",
        "#sf-modes label span { font-weight: 650; font-size: 14.5px; }",
        "#sf-modes label::before { content: ''; width: 26px; height: 26px; margin-bottom: 8px; background-color: currentColor; opacity: .85; "
        "-webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-size: contain; mask-size: contain; "
        "-webkit-mask-position: center; mask-position: center; }",
        "#sf-modes label::after { font-size: 12px; opacity: .8; line-height: 1.35; font-weight: 400; }",
        "#sf-modes label.selected { border-color: #ea580c !important; background: rgba(234,88,12,.14) !important; "
        "box-shadow: 0 0 0 1px #ea580c inset; }",
        "#sf-modes label.selected::before { color: #ea580c; opacity: 1; }",
        "@media (max-width: 860px) { #sf-modes .wrap { grid-template-columns: repeat(2, minmax(0, 1fr)); } }",
    ]
    for label, body, text in MODES:
        sel = f"#sf-modes label[data-testid=\"{label}-radio-label\"]"
        svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' {ICON_STYLE}>{body}</svg>"
        css.append(f"{sel}::before {{ -webkit-mask-image: url(\"data:image/svg+xml;utf8,{svg}\"); mask-image: url(\"data:image/svg+xml;utf8,{svg}\"); }}")
        css.append(f"{sel}::after {{ content: \"{text}\"; }}")
    return "\n".join(css)


EXTRA_CSS = """
.sf-hero { padding: 18px 0 0; }
.sf-hero h1 { font-size: 34px; letter-spacing: -0.03em; background: linear-gradient(90deg, #fb923c, #ea580c 60%, #c2410c);
              -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent !important; color: transparent !important; width: fit-content; }
.sf-hero p { max-width: 640px; }
.gradio-container .block, .gradio-container .form { border-color: rgba(128,128,128,.22) !important; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.gradio-container button.primary { box-shadow: 0 6px 18px rgba(234,88,12,.28); transition: transform .12s, box-shadow .12s; }
.gradio-container { overflow-x: clip !important; overflow-y: visible !important; }          /* so the primary button can stay in view while the form scrolls */
.gradio-container button.primary { position: sticky; bottom: 14px; z-index: 30; }
.gradio-container button.primary:hover { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(234,88,12,.38); }
@media (max-width: 640px) { .gradio-container { padding: 0 6px !important; } .gradio-container .main, .gradio-container .fillable { padding-left: 4px !important; padding-right: 4px !important; } .gradio-container .column, .gradio-container .block { min-width: 0 !important; } .gradio-container .row { flex-wrap: wrap !important; } }
.info-text, .block-info, .gradio-container .info { opacity: 1 !important; color: var(--neutral-600, #475569) !important; }
.dark .info-text, .dark .block-info, .dark .gradio-container .info { color: var(--neutral-400, #94a3b8) !important; }   /* readable hints (WCAG AA), not pale grey */
.gradio-container :is(button, input, select, textarea, summary, [tabindex]):focus-visible { outline: 2px solid #ea580c !important; outline-offset: 2px; }
.gradio-container { padding-bottom: 96px !important; }          /* room under the last control, so the floating button never hides it */
@media (prefers-reduced-motion: reduce) { .gradio-container *, .gradio-container *::before, .gradio-container *::after { transition: none !important; animation: none !important; } .gradio-container button:hover, #sf-modes label:hover { transform: none !important; } }
@media (max-width: 900px) { #sf-projects .grid-container, #sf-templates .grid-container { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; } }
@media (max-width: 560px) { #sf-projects .grid-container, #sf-templates .grid-container { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; } }
#sf-projects .grid-container { max-height: 460px; overflow-y: auto; }          /* a long history scrolls inside its box instead of pushing the page down */
.sf-progress { padding: 14px 16px 12px; border-radius: 14px; border: 1px solid rgba(128,128,128,.25); background: rgba(128,128,128,.06); }
.gradio-container .accordion > button, .gradio-container details > summary { font-weight: 600; }
""" + mode_card_css()
