from textual.theme import Theme

# Houston — space-inspired theme with cool blues, minty greens, and soft purples
# Created by Astro team, featuring cosmic aesthetics
THEMES = [
    Theme(
        name="houston",
        primary="#5DADE2",  # cool blue (space blue)
        secondary="#58D68D",  # minty green accent
        warning="#F39C12",  # cosmic amber
        error="#E74C3C",  # mars red
        success="#58D68D",  # same minty green
        accent="#9B59B6",  # soft purple (nebula)
        foreground="#ECF0F1",  # starlight white
        background="#1B2631",  # deep space dark
        surface="#212F3D",  # space surface
        panel="#17202A",  # darker space panel
        dark=True,
        variables={
            "input-selection-background": "#5DADE2 35%",  # blue selection
            "button-color-foreground": "#1B2631",
        },
    )
]
