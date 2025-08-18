from textual.theme import Theme

# Tomorrow (Light) — from the Tomorrow color schemes
THEMES = [
    Theme(
        name="tomorrow",
        primary="#4271AE",  # blue
        secondary="#3E999F",  # cyan
        warning="#EAB700",  # yellow
        error="#C82829",  # red
        success="#718C00",  # green
        accent="#8959A8",  # purple
        foreground="#4D4D4C",  # text
        background="#FFFFFF",  # base
        surface="#F5F5F5",  # editor bg
        panel="#E9E9E9",  # side/panel
        dark=False,
        variables={
            "input-selection-background": "#D6D6D6 40%",
            "button-color-foreground": "#FFFFFF",
        },
    )
]
