from fastapi import HTTPException
from starlette.requests import Request


def parse_terminal_id(raw_value: str | int | None) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Terminal inválida en la solicitud")
    if value < 1:
        raise HTTPException(status_code=400, detail="terminal_id debe ser mayor o igual a 1")
    return value


def get_requested_terminal_id(request: Request | None) -> int | None:
    if request is None:
        return None
    header_value = request.headers.get("X-Terminal-Id")
    if not header_value:
        return None
    return parse_terminal_id(header_value)
