from fastapi import APIRouter, Depends, status

from server.domain.repository import AssetRepository, get_asset_repository
from server.schemas.assets import ProjectCreateRequest, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    repository: AssetRepository = Depends(get_asset_repository),
) -> ProjectResponse:
    return ProjectResponse.model_validate(repository.create_project(payload))
