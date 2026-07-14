from app.database.models import Prompt
from app.repositories.ai_run_repository import AIRunRepository
from app.services.ai_service import AIService

class AIRunService:
    def __init__(self, run_repo: AIRunRepository, ai_service: AIService):
        self.run_repo = run_repo
        self.ai_service = ai_service

    async def run_prompt_models(self, prompt: Prompt) -> list[dict]:
        results = []
        for link in prompt.models:
            model = link.model
            request_text = prompt.text
            try:
                response_text = await self.ai_service.run_prompt(model.model_key, request_text)
                run = await self.run_repo.create(
                    prompt_id=prompt.id,
                    ai_model_id=model.id,
                    request_text=request_text,
                    response_text=response_text,
                    status="success",
                )
                results.append({
                    "id": run.id,
                    "ai_model_id": model.id,
                    "model_key": model.model_key,
                    "status": "success",
                })
            except Exception as exc:
                run = await self.run_repo.create(
                    prompt_id=prompt.id,
                    ai_model_id=model.id,
                    request_text=request_text,
                    status="failed",
                    error_message=str(exc),
                )
                results.append({
                    "id": run.id,
                    "ai_model_id": model.id,
                    "model_key": model.model_key,
                    "status": "failed",
                    "error_message": str(exc),
                })
        return results
