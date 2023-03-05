from pydantic import BaseModel, Extra
from .aria2c import Aria2Client

aria2c = Aria2Client()
aria2c.init_client()


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""
