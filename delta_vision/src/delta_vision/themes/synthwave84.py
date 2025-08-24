from textual.theme import Theme

# SynthWave '84 — neon dreams and retro cyberpunk vibes
# Inspired by 80s synthwave music and neon aesthetics
THEMES = [
    Theme(
        name="synthwave-84",
        primary="#FF2E8A",  # hot pink neon
        secondary="#2DE2E6",  # electric cyan
        warning="#FFAF00",  # neon amber
        error="#FF073A",  # neon red
        success="#39FF14",  # electric green
        accent="#9D4EDD",  # neon purple
        foreground="#F5F5F5",  # bright white
        background="#0B0C10",  # deep black
        surface="#1A1A2E",  # midnight blue
        panel="#16213E",  # dark neon blue
        dark=True,
        variables={
            "input-selection-background": "#FF2E8A 40%",  # pink glow selection
            "button-color-foreground": "#0B0C10",
        },
    )
]
