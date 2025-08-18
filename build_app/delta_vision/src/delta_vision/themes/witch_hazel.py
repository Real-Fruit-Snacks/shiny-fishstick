from textual.theme import Theme

# Witch Hazel — aligned to the official palette from https://github.com/theacodes/witchhazel
# Key references (VS Code theme JSON):
# - editor.background: #433E56
# - editor.foreground: #F8F8F2
# - selection: #8077A8
# - line highlight: #716799
# - accents: aqua #31CAE3 / #2CB5CC, lavender #C5A3FF, mint #C2FFDF, pink #FF81AD, yellow #FFF781
THEMES = [
    Theme(
        name="witch-hazel",
        primary="#716799",  # prominent purple (tabs/status/line highlight)
        secondary="#31CAE3",  # aqua accent
        warning="#FFF781",  # soft yellow warning
        error="#FF81AD",  # pinkish error
        success="#C2FFDF",  # mint success
        accent="#C5A3FF",  # lavender accent
        foreground="#F8F8F2",  # light text
        background="#433E56",  # base background
        surface="#3C374D",  # editor/widget bg
        panel="#353144",  # activity/sidebar bg
        dark=True,
        variables={
            # Match selection color used throughout the theme
            "input-selection-background": "#8077A8",
            # Favor dark text on bright buttons by default (app may override per-widget)
            "button-color-foreground": "#433E56",
        },
    )
]
