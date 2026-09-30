"""The platform list, kept out of data_generator so importing it does not pull
in faker. Both the API server and the CLI need this list, and only the CLI
needs to actually generate creators."""

PLATFORMS = [
    "Instagram", "TikTok", "YouTube", "Threads", "X",
    "Pinterest", "LinkedIn", "Snapchat", "Twitch",
]
