# app/models/__init__.py

# 1. Importamos as classes de seus respectivos arquivos
from .user import User
from .video import Video
from .processingJob import ProcessingJob
from .clip import Clip
from .candidates import Candidate

# 2. Definimos o __all__ para expor explicitamente o que essa pasta exporta.
# Isso permite que em outros arquivos você faça:
# from app.models import User, Video, ProcessingJob, Clip, Candidate
__all__ = [
    "User",
    "Video",
    "ProcessingJob",
    "Clip",
    "Candidate",
]