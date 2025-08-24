from textual.theme import Theme

# HackTheBox — cybersecurity-inspired terminal colors
# Bright greens and blues with dark backgrounds for that hacker aesthetic
THEMES = [
    Theme(
        name="hackthebox",
        primary="#9fef00",  # bright green (signature HTB color)
        secondary="#2ee7b6",  # cyan accent
        warning="#ffaf00",  # orange/amber warning
        error="#ff3e3e",  # bright red error
        success="#9fef00",  # same as primary green
        accent="#004cff",  # electric blue
        foreground="#c5d1eb",  # light blue-gray text
        background="#111927",  # very dark blue-gray
        surface="#2e3436",  # dark gray surface
        panel="#0a0f1a",  # even darker panel
        dark=True,
        variables={
            "input-selection-background": "#9fef00 30%",  # green selection
            "button-color-foreground": "#111927",
        },
    )
]
