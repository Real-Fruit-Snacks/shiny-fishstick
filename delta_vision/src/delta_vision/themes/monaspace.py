from textual.theme import Theme

# Monaspace — clean, minimal theme to complement the GitHub Monaspace font family
# Focus on readability and typography with subtle, professional colors
THEMES = [
    Theme(
        name="monaspace",
        primary="#0969DA",  # GitHub blue
        secondary="#6F42C1",  # GitHub purple
        warning="#BF8700",  # amber
        error="#DA3633",  # GitHub red
        success="#1A7F37",  # GitHub green
        accent="#8250DF",  # light purple accent
        foreground="#24292F",  # near-black text
        background="#FFFFFF",  # pure white
        surface="#F6F8FA",  # light gray surface
        panel="#F0F3F6",  # slightly darker panel
        dark=False,
        variables={
            "input-selection-background": "#0969DA 20%",  # subtle blue selection
            "button-color-foreground": "#FFFFFF",
        },
    )
]
