from textual.theme import Theme

# Kanagawa — inspired by Katsushika Hokusai's famous painting
# Muted, sophisticated palette with traditional Japanese aesthetics
THEMES = [
    Theme(
        name="kanagawa",
        primary="#7E9CD8",  # crystalBlue (main accent)
        secondary="#6A9589",  # waveAqua1 (teal accent)
        warning="#DCA561",  # autumnYellow (gold/amber)
        error="#C34043",  # autumnRed (muted red)
        success="#76946A",  # autumnGreen (sage green)
        accent="#957FB8",  # oniViolet (purple accent)
        foreground="#DCD7BA",  # fujiWhite (main text)
        background="#1F1F28",  # sumiInk3 (main background)
        surface="#2A2A37",  # sumiInk4 (editor/surface)
        panel="#16161D",  # sumiInk0 (darker panels)
        dark=True,
        variables={
            "input-selection-background": "#54546D 40%",  # sumiInk6 with opacity
            "button-color-foreground": "#1F1F28",
        },
    )
]
