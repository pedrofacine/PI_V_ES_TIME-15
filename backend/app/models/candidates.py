import uuid
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.job import ProcessingJob

class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    
    # Assinatura única gerada pelo Fast Scan (ex: "8_#ff0000")
    signature: str 
    
    name: str
    number: int
    color_hex: Optional[str] = None
    image_path: str
    
    # A MÁGICA ESTÁ AQUI: Essa flag avisa o Frontend para abrir o Modal!
    is_target: bool = Field(default=False) 

    job: Optional["ProcessingJob"] = Relationship(back_populates="candidates")