from textual.theme import Theme

# One Dark — based on Atom/One Dark Pro palettes
THEMES = [
    Theme(
        name="one-dark",
        primary="#61AFEF",  # blue
        secondary="#56B6C2",  # cyan
        warning="#E5C07B",  # yellow/gold
        error="#E06C75",  # red
        success="#98C379",  # green
        accent="#C678DD",  # purple
        foreground="#ABB2BF",  # text
        background="#282C34",  # base
        surface="#21252B",  # editor bg
        panel="#1E222A",  # side/panel
        dark=True,
        variables={
            "input-selection-background": "#3E4451 40%",
            "button-color-foreground": "#282C34",
        },
    )
]
