"""Seed seven prior calendar days of analytics data for one project."""

import argparse
import asyncio
import json
from datetime import date, datetime, time, timedelta, timezone


def history_dates(days: int, today: date | None = None) -> list[date]:
    if days < 1:
        raise ValueError("days must be at least 1")
    today = today or date.today()
    return [today - timedelta(days=offset) for offset in range(days, 0, -1)]


def missing_history_dates(days: int, existing_dates: set[date], today: date | None = None) -> list[date]:
    return [day for day in history_dates(days, today) if day not in existing_dates]


async def seed(project_id: int, days: int) -> int:
    from sqlalchemy import func, select

    from app.database.connection import async_session_maker
    from app.database.models import AIModel, AIRun, Brand, Project, ProjectBrand, Prompt, PromptModel, RunBrand

    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"project {project_id} was not found")

        pairs = (await session.execute(
            select(Prompt, AIModel)
            .join(PromptModel, PromptModel.prompt_id == Prompt.id)
            .join(AIModel, AIModel.id == PromptModel.ai_model_id)
            .where(Prompt.project_id == project_id, Prompt.is_active, AIModel.is_active)
            .order_by(Prompt.id, AIModel.id)
        )).all()
        if not pairs:
            raise ValueError(f"project {project_id} has no active prompt/model pairs")
        existing_dates = set((await session.scalars(
            select(func.date(AIRun.created_at)).join(Prompt).where(Prompt.project_id == project_id)
        )).all())
        dates = missing_history_dates(days, existing_dates)

        owned = await session.scalar(
            select(ProjectBrand).where(ProjectBrand.project_id == project_id, ProjectBrand.kind == "owned")
        )
        owned_name = owned.name if owned else project.name
        brand_specs = [(owned_name, None, "owned")] + [
            (f"Seed Competitor {letter}", f"seed-competitor-{letter.lower()}.invalid", "competitor")
            for letter in "ABCD"
        ]
        brands: list[Brand] = []
        for name, domain, kind in brand_specs:
            brand = await session.scalar(select(Brand).where(func.lower(Brand.name) == name.lower()))
            if brand is None:
                brand = Brand(name=name, domain=domain)
                session.add(brand)
                await session.flush()
            brands.append(brand)
            if domain and not await session.scalar(
                select(ProjectBrand.id).where(ProjectBrand.project_id == project_id, ProjectBrand.domain == domain)
            ):
                session.add(ProjectBrand(project_id=project_id, name=name, domain=domain, kind=kind, brand_id=brand.id))

        created = 0
        for day_index, day in enumerate(dates):
            run_at = datetime.combine(day, time(12), tzinfo=timezone.utc)
            for prompt, model in pairs:
                marker = f"[seed-history:{project_id}:{day.isoformat()}]"
                existing = await session.scalar(
                    select(AIRun.id).where(
                        AIRun.prompt_id == prompt.id,
                        AIRun.ai_model_id == model.id,
                        AIRun.request_text.startswith(marker),
                    )
                )
                if existing:
                    continue
                response = json.dumps({"brands": [brand.name for brand in brands]}, ensure_ascii=False)
                run = AIRun(
                    prompt_id=prompt.id,
                    ai_model_id=model.id,
                    request_text=f"{marker} {prompt.text}",
                    response_text=response,
                    status="success",
                    extraction_status="completed",
                    processed_at=run_at,
                    created_at=run_at,
                    completed_at=run_at + timedelta(seconds=10),
                )
                session.add(run)
                await session.flush()
                for brand_index, brand in enumerate(brands):
                    base_rank = 8 - day_index if brand_index == 0 else brand_index * 2
                    variation = (prompt.id + model.id + day_index) % 2
                    session.add(RunBrand(
                        ai_run_id=run.id,
                        brand_id=brand.id,
                        raw_name=brand.name,
                        rank=max(1, base_rank + variation),
                        confidence=round(0.95 - brand_index * 0.06, 2),
                        created_at=run_at,
                    ))
                created += 1
        await session.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    print(f"Created {asyncio.run(seed(args.project_id, args.days))} seed runs.")


if __name__ == "__main__":
    main()
