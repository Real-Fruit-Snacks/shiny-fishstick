from textual.theme import Theme

# Hotdog Stand — playful high-contrast scheme inspired by classic Windows
THEMES = [
    Theme(
        name="hotdog-stand",
        primary="#FFFF00",  # bright yellow (window areas)
        secondary="#FFFFFF",  # white
        warning="#FFFF00",  # yellow warnings (stay in 16‑color look)
        error="#FF0000",  # red
        success="#00FF00",  # green
        accent="#000000",  # black accents/borders
        foreground="#000000",  # black text
        background="#FF0000",  # red background
        surface="#FF0000",  # red surfaces to make background dominant
        panel="#FF0000",  # red panels/containers
        dark=False,
        variables={
            # Windows 3.x typically uses a dark/navy selection highlight
            "input-selection-background": "#000080 45%",
            "button-color-foreground": "#000000",
        },
    )
]
