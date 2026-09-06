import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models import AIModel, AIRun, Brand, Project, Prompt, PromptModel, RunBrand
from app.dependencies import get_session

router = APIRouter(prefix="/internal", tags=["internal"])


async def require_api_key(x_api_key: str = Header(...)):
    if not settings.INTERNAL_API_KEY or not hmac.compare_digest(x_api_key.encode(), settings.INTERNAL_API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.get("/daily-report", dependencies=[Depends(require_api_key)])
async def daily_report(project_id: int, session: AsyncSession = Depends(get_session)):
    project = await session.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="پروژه یافت نشد")

    prompts = (
        await session.execute(
            select(Prompt.id, Prompt.text)
            .where(Prompt.project_id == project_id, Prompt.is_active.is_(True))
            .order_by(Prompt.id)
        )
    ).all()

    model_rows = (
        await session.execute(
            select(PromptModel.prompt_id, AIModel.id.label("model_id"), AIModel.name)
            .join(AIModel, AIModel.id == PromptModel.ai_model_id)
            .join(Prompt, Prompt.id == PromptModel.prompt_id)
            .where(Prompt.project_id == project_id, AIModel.is_active.is_(True))
            .order_by(PromptModel.prompt_id, AIModel.name)
        )
    ).all()

    ranked_runs = (
        select(
            AIRun.id,
            AIRun.prompt_id,
            AIRun.ai_model_id,
            func.row_number()
            .over(
                partition_by=(AIRun.prompt_id, AIRun.ai_model_id),
                order_by=(AIRun.created_at.desc(), AIRun.id.desc()),
            )
            .label("rn"),
        )
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .where(Prompt.project_id == project_id, AIRun.status == "success")
        .subquery()
    )

    latest_brand_rows = (
        await session.execute(
            select(
                ranked_runs.c.prompt_id,
                ranked_runs.c.ai_model_id,
                Brand.id.label("brand_id"),
                Brand.name,
                Brand.domain,
                RunBrand.rank,
            )
            .join(RunBrand, RunBrand.ai_run_id == ranked_runs.c.id)
            .join(Brand, Brand.id == RunBrand.brand_id)
            .where(ranked_runs.c.rn == 1)
            .order_by(ranked_runs.c.prompt_id, ranked_runs.c.ai_model_id, RunBrand.rank)
        )
    ).all()

    visibility_rows = (
        await session.execute(
            select(AIRun.prompt_id, AIRun.ai_model_id, RunBrand.brand_id, func.count(distinct(AIRun.id)))
            .select_from(RunBrand)
            .join(AIRun, AIRun.id == RunBrand.ai_run_id)
            .join(Prompt, Prompt.id == AIRun.prompt_id)
            .where(Prompt.project_id == project_id, AIRun.status == "success")
            .group_by(AIRun.prompt_id, AIRun.ai_model_id, RunBrand.brand_id)
        )
    ).all()

    visibility: dict[tuple[int, int, int], int] = {
        (prompt_id, model_id, brand_id): count for prompt_id, model_id, brand_id, count in visibility_rows
    }

    brands_by_run: dict[tuple[int, int], list[dict]] = {}
    for prompt_id, model_id, brand_id, name, domain, rank in latest_brand_rows:
        brands_by_run.setdefault((prompt_id, model_id), []).append(
            {"name": name, "domain": domain, "rank": rank, "visibility": visibility.get((prompt_id, model_id, brand_id), 0)}
        )

    models_by_prompt: dict[int, list[dict]] = {}
    for prompt_id, model_id, model_name in model_rows:
        brands = brands_by_run.get((prompt_id, model_id))
        if not brands:
            continue
        models_by_prompt.setdefault(prompt_id, []).append({"model_id": model_id, "model_name": model_name, "brands": brands})

    result_prompts = [
        {"prompt_id": prompt_id, "text": text, "models": models_by_prompt.get(prompt_id, [])}
        for prompt_id, text in prompts
    ]

    return {
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompts": result_prompts,
    }
