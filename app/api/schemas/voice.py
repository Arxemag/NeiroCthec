from pydantic import BaseModel


class VoiceOut(BaseModel):
    """Голос для списка в API: id, имя, роль (диктор/мужской/женский), URL сэмпла (относительный)."""
    id: str
    name: str
    role: str  # narrator | male | female
    sample_url: str  # относительный путь, например /voices/{id}/sample
