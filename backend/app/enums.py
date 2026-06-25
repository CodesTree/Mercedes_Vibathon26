from enum import StrEnum

class Priority(StrEnum):     LOW="low"; NORMAL="normal"; HIGH="high"
class MsgStatus(StrEnum):    UNREAD="unread"; SUMMARIZED="summarized"; REPLIED="replied"; SILENCED="silenced"; SEND_FAILED="send_failed"
class RelSource(StrEnum):    SEED="seed"; AI="ai_inferred"; USER="user_tagged"; UNKNOWN="unknown"
class Relationship(StrEnum): BOSS="boss"; FAMILY="family"; FRIEND="friend"; COLLEAGUE="colleague"; MARKETING="marketing"
class EtaSource(StrEnum):    TOMTOM="tomtom"; SIMULATOR="simulator"
class ReplyMode(StrEnum):    TEXT="text"; VOICE="voice"
class AudioFmt(StrEnum):     WEBM="webm_opus"; OGG="ogg_opus"
class AutoType(StrEnum):     LATE="late_responder"; PRECOOL="cabin_precool"; DEPART="departure_plan"; TEXT_REPLY="text_reply"; VOICE_REPLY="voice_reply"
class AutoStatus(StrEnum):   OK="ok"; ERROR="error"; SKIPPED="skipped"
