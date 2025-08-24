from textual.theme import Theme

# Cyberpunk 2077 — inspired by the game's official color palette
# Featuring iconic cyan, yellow, and blue with dystopian dark tones
THEMES = [
    Theme(
        name="cyberpunk-2077",
        primary="#02D7F2",  # signature cyberpunk cyan
        secondary="#007AFF",  # electric blue
        warning="#F2E900",  # bright cyberpunk yellow
        error="#FF1111",  # cyberpunk red
        success="#00FF88",  # neon green
        accent="#B942E6",  # cyber purple
        foreground="#E6E6FA",  # light lavender text
        background="#0D0D0D",  # near black
        surface="#1A1A1A",  # dark charcoal
        panel="#111111",  # darker panel
        dark=True,
        variables={
            "input-selection-background": "#02D7F2 35%",  # cyan selection
            "button-color-foreground": "#0D0D0D",
        },
    )
]
