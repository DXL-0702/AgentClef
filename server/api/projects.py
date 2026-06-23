from uuid import UUID

from fastapi import APIRouter, Depends, status

from server.api.errors import raise_api_error
from server.domain.repository import AssetRepository, get_asset_repository
from server.schemas.assets import ProjectCreateRequest, ProjectResponse
from shared.schemas.score import DraftScore

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    repository: AssetRepository = Depends(get_asset_repository),
) -> ProjectResponse:
    return ProjectResponse.model_validate(repository.create_project(payload))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    repository: AssetRepository = Depends(get_asset_repository),
) -> ProjectResponse:
    project = repository.get_project(project_id)
    if project is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="project_not_found",
            message="project not found",
        )
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/draft", response_model=DraftScore)
def get_project_draft_score(
    project_id: UUID,
    repository: AssetRepository = Depends(get_asset_repository),
) -> DraftScore:
    project = repository.get_project(project_id)
    if project is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="project_not_found",
            message="project not found",
        )

    draft_score = repository.get_draft_score_for_project(project_id)
    if draft_score is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="draft_score_not_found",
            message="draft score not found",
        )
    return DraftScore.model_validate(draft_score.payload)
