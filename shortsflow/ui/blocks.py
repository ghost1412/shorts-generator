"""Pieces of the browser app that every flow shares, written once so they look and behave the same everywhere.

`gr` (gradio) and `web_args` are passed in, so this module imports without gradio and the tests can import it.
"""


def look_block(gr, web_args, prefix_info="", with_shape=True, open_=False):
    """Template gallery (click a picture to choose), covers, template text and frame shape.

    Returns the components in the order [template, intro, outro, six text boxes] + [frame shape when `with_shape`]."""
    with gr.Accordion("🎨 Look: templates, covers and frame shape (click to open)", open=open_):
        tpl = gr.Dropdown(web_args.VISUAL_TEMPLATE_CHOICES, value="none", label="Visual template",
                          info="A designed look drawn over the picture. Click a picture below or pick from this list. Turns on animated captions." + prefix_info)
        shown = [(label, name) for label, name in web_args.VISUAL_TEMPLATE_CHOICES if web_args.template_preview(name)]
        if shown:
            gal = gr.Gallery([(web_args.template_preview(n), label) for label, n in shown], columns=5, height=260, allow_preview=False,
                             show_label=False, interactive=False)
            names = [n for _, n in shown]

            def pick(evt: gr.SelectData):          # the type hint is what makes Gradio pass the clicked picture
                return gallery_pick(names, evt.index)
            gal.select(pick, None, tpl)
        with gr.Row():
            intro = gr.Dropdown(web_args.COVER_CHOICES, value="none", label="Intro cover",
                                info="Opens over the first second (tiles break apart, doors, iris, blinds, fade).")
            outro = gr.Dropdown(web_args.COVER_CHOICES, value="none", label="Outro cover", info="Closes over the last second.")
        with gr.Accordion("Text for the template (only what you type is drawn)", open=False):
            texts = [gr.Textbox(label=label, placeholder=ph, max_lines=1) for label, ph in (
                ("Speaker name", "Alex Morgan"), ("Role", "Host"), ("Show or channel", "My Show"), ("Handle", "@myshow"),
                ("Headline", "A line for the top bar"), ("Closing line", "Follow @myshow for more"))]
        shape = gr.Dropdown(web_args.SHAPE_CHOICES, value="9:16", label="Frame shape",
                            info="For shorts cut from a video. The highlights video is always 16:9.") if with_shape else None
    return [tpl, intro, outro, *texts] + ([shape] if shape is not None else [])


def gallery_pick(names, index):
    """The template name for a clicked gallery picture ('none' for an index that does not exist)."""
    return names[index] if isinstance(index, int) and 0 <= index < len(names) else "none"
