def success(data=None, message="OK", status=200):
    return {"ok": True, "message": message, "data": data or {}, "status": status}


def error(message="Request failed", code="bad_request", status=400, details=None):
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
        "status": status,
    }
