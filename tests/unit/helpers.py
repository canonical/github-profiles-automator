import base64


def as_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")
