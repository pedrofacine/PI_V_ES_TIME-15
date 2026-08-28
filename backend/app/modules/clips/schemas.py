from pydantic import BaseModel


class ConfirmPlayerRequest(BaseModel):
    candidate_signature: str
    start_ts: int = 0
    end_ts: int = 0
