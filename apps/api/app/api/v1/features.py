from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.auth import FeaturesResponse

router = APIRouter(tags=["features"])


@router.get("/features", response_model=FeaturesResponse)
def get_features(settings: Settings = Depends(get_settings)) -> FeaturesResponse:
    return FeaturesResponse(features=settings.feature_map())
