from os import getenv

from dotenv import load_dotenv

load_dotenv()

MONGO_DSN = getenv("MONGO_DSN")

__version__ = '1.0.0'