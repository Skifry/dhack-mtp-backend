from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Optional

class GeoBoundZK(BaseModel):
    points: List[Tuple[float, float]]
    livingSquare: int
    workingSquare: int

class GeoCalculateRequest(BaseModel):
    projects: List[GeoBoundZK]

class GeoCalculation(BaseModel):
    metroLoad: Dict
    roadLoad: Optional[Dict] = Field(None)
