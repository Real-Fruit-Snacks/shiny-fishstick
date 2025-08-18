from textual.theme import Theme

# Material Theme (dark) — palette inspired by popular VS Code "Material Theme"
# Colors selected from well-known Material Theme variants (open palettes),
# avoiding any proprietary assets.
THEMES = [
    Theme(
        name="material",
        primary="#82AAFF",  # material blue (editor blue)
        secondary="#80CBC4",  # teal accent
        warning="#FFCB6B",  # amber
        error="#F07178",  # soft red
        success="#C3E88D",  # light green
        accent="#C792EA",  # purple
        foreground="#EEFFFF",  # near-white text (material fg)
        background="#263238",  # dark blue-grey
        surface="#2E3C43",  # editor background
        panel="#1E272C",  # panel/sidebar
        dark=True,
        variables={
            "input-selection-background": "#314549 40%",
            "button-color-foreground": "#263238",
        },
    )
]
