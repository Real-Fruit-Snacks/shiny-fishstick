from textual.theme import Theme

# Dainty — soft, delicate pastel theme with gentle colors
# Inspired by subtle, elegant aesthetics with good readability
THEMES = [
    Theme(
        name="dainty",
        primary="#8B5FBF",  # soft lavender purple
        secondary="#5FB3D4",  # gentle sky blue
        warning="#E6A85C",  # warm peach
        error="#D47D7D",  # soft coral red
        success="#7FB069",  # muted sage green
        accent="#C67DBF",  # dusty rose
        foreground="#2D3748",  # charcoal gray text
        background="#FAF9F7",  # warm off-white
        surface="#F1EFF2",  # soft lavender tint
        panel="#E8E5EA",  # gentle gray-lavender
        dark=False,
        variables={
            "input-selection-background": "#8B5FBF 25%",  # soft purple selection
            "button-color-foreground": "#FAF9F7",
        },
    )
]
