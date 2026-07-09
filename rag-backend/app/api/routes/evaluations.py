import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models import EvaluationCase, User
from app.schemas import (
    EvaluationCaseCreateRequest,
    EvaluationCaseResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from app.services.evaluation_service import (
    build_evaluation_summary,
    create_evaluation_case,
    delete_evaluation_case,
    list_evaluation_cases,
    run_evaluation_case,
    serialize_evaluation_case,
)

router = APIRouter(prefix="/admin/evaluations", tags=["admin-evaluations"])
logger = logging.getLogger(__name__)


@router.get("/cases", response_model=list[EvaluationCaseResponse])
def get_evaluation_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[EvaluationCaseResponse]:
    _ = current_user
    return [serialize_evaluation_case(case) for case in list_evaluation_cases(db)]


@router.post("/cases", response_model=EvaluationCaseResponse)
def add_evaluation_case(
    request: EvaluationCaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> EvaluationCaseResponse:
    try:
        _ = current_user
        return serialize_evaluation_case(create_evaluation_case(db, request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Create evaluation case failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/cases/{case_id}")
def remove_evaluation_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _ = current_user
    if not delete_evaluation_case(db, case_id):
        raise HTTPException(status_code=404, detail="Evaluation case not found")
    return {"success": True, "case_id": case_id}


@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluations(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> EvaluationRunResponse:
    try:
        _ = current_user
        query = db.query(EvaluationCase)
        if request.case_ids:
            query = query.filter(EvaluationCase.id.in_(request.case_ids))
        cases = query.order_by(EvaluationCase.created_at.asc()).all()
        results = [
            run_evaluation_case(
                db,
                case,
                override_use_rerank=request.use_rerank,
                override_top_k=request.top_k,
            )
            for case in cases
        ]
        return EvaluationRunResponse(
            summary=build_evaluation_summary(results),
            results=results,
        )
    except Exception as exc:
        logger.exception("Run evaluations failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
