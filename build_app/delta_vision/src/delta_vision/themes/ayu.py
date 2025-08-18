from textual.theme import Theme

# ayu-mirage theme based on ayu-colors mirage palette
THEMES = [
    Theme(
        name="ayu-mirage",
        primary="#FFCC66",  # accent
        secondary="#73D0FF",  # blue (entity)
        warning="#FFAD66",  # keyword
        error="#FF6666",  # common.error
        success="#87D96C",  # vcs.added
        accent="#5CCFE6",  # tag (teal accent)
        foreground="#CCCAC2",  # editor.fg
        background="#1F2430",  # ui.bg
        surface="#242936",  # editor.bg
        panel="#1C212B",  # ui.panel.bg
        dark=True,
        variables={
            "input-selection-background": "#409FFF 25%",  # editor.selection.active
            "button-color-foreground": "#1F2430",
        },
    )
]
