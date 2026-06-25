from ..enums import MsgStatus as S

_ALLOWED = {
    S.UNREAD:      {S.SUMMARIZED, S.SILENCED},
    S.SUMMARIZED:  {S.SUMMARIZED, S.REPLIED, S.SILENCED, S.SEND_FAILED},
    S.REPLIED:     set(),
    S.SILENCED:    {S.SUMMARIZED, S.REPLIED},
    S.SEND_FAILED: {S.REPLIED},
}


class Conflict(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def apply_status(msg, new: S):
    cur = S(msg.status)
    if new == cur:
        return msg
    if new not in _ALLOWED[cur]:
        raise Conflict(code="INVALID_TRANSITION",
                       detail=f"{cur} → {new} is not allowed")
    msg.status = new
    return msg
