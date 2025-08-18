from textual.theme import Theme

# Zenburn — low-contrast dark theme
THEMES = [
    Theme(
        name="zenburn",
        primary="#8CD0D3",  # cyan
        secondary="#94BFF3",  # blue
        warning="#E3CEAB",  # yellow
        error="#CC9393",  # red
        success="#7F9F7F",  # green
        accent="#DC8CC3",  # magenta
        foreground="#DCDCCC",  # text
        background="#3F3F3F",  # base
        surface="#2B2B2B",  # editor bg
        panel="#242424",  # side/panel
        dark=True,
        variables={
            "input-selection-background": "#5F5F5F 40%",
            "button-color-foreground": "#3F3F3F",
        },
    )
]
