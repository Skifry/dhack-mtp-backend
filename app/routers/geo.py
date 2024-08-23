from fastapi import APIRouter
from app.data import schemas
from app.data import geo

router = APIRouter(prefix="/geo")

@router.post('/calculate')
async def calculateGeoBox(request: schemas.GeoCalculateRequest) -> schemas.GeoCalculation:
    return geo.calcTraffic(request.projects)