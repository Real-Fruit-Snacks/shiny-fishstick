from textual.theme import Theme

# Tomorrow Night — dark variant of Tomorrow
THEMES = [
    Theme(
        name="tomorrow-night",
        primary="#81A2BE",  # blue
        secondary="#8ABEB7",  # cyan
        warning="#F0C674",  # yellow
        error="#CC6666",  # red
        success="#B5BD68",  # green
        accent="#B294BB",  # purple
        foreground="#C5C8C6",  # text
        background="#1D1F21",  # base
        surface="#282A2E",  # editor bg
        panel="#1A1C1E",  # side/panel
        dark=True,
        variables={
            "input-selection-background": "#373B41 40%",
            "button-color-foreground": "#1D1F21",
        },
    )
]
