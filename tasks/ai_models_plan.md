# AI Model Management Plan

## Context
مدیریت مدل‌های AI قابل انتخاب برای اجرای Promptها از طریق یک AI Gateway
شبیه OpenRouter. تمام درخواست‌ها از یک Base URL عبور می‌کنند و فقط `model_key` متفاوت است.

## Tasks

### Task 1: Add AIModel + prompt_models models
- `AIModel`: id, name, provider, model_key, is_active, created_at
- `PromptModel` (bridge): id, prompt_id, ai_model_id
- رابطه many-to-many بین Prompt و AIModel
- Dependencies: None

### Task 2: AIModelRepository
- `list_active()` → فقط مدل‌های فعال
- `get_by_id()`, `create()`
- Dependencies: Task 1

### Task 3: AIModelService + schemas
- `list_active_models()`
- `AIModelRead` schema
- Dependencies: Task 2

### Task 4: AI Models router
- `GET /ai-models` → لیست مدل‌های فعال (برای فرانت‌اند)
- Dependencies: Task 3

### Task 5: Wire into main + gateway config
- include router
- `AI_GATEWAY_BASE_URL` در settings (ponytail: اجرای واقعی بعداً)
- Dependencies: Task 4

### Task 6: Runnable self-check test
- Dependencies: Task 1-5

## Boundaries
- هیچ سرویس جداگانه‌ای برای Provider ساخته نشود
- تمام درخواست‌ها از AI Gateway عبور کنند (constraint برای آینده)
- پیام‌های خطا فارسی
