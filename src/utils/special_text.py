def color_text(text: str, color: int) -> str:
    return f"\033[{color + 30}m{text}\033[0m"

def hyperlink(text: str, url: str) -> str:
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"