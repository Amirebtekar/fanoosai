# SPEC: Prompt Management System

## Objective
پیاده‌سازی سیستم مدیریت Prompt برای هر پروژه با قوانین سختگیرانه برای حفظ یکپارچگی داده‌ها.

## Commands/API

### Endpoints
1. **POST `/projects/{project_id}/prompts`** - ایجاد Prompt جدید
   - Request Body: `{text: str}`
   - Validation: پروژه وجود داشته باشد، حداکثر 10 prompt فعال
   - Response: `PromptRead`

2. **GET `/projects/{project_id}/prompts`** - لیست Prompt های پروژه
   - Query Params: `include_archived=false` (default)
   - Response: `List[PromptRead]`

3. **GET `/prompts/{prompt_id}`** - جزئیات یک Prompt
   - Response: `PromptRead`

4. **DELETE `/prompts/{prompt_id}`** - Archive کردن Prompt
   - Validation: حداقل 1 prompt فعال باقی بماند
   - Response: 204 No Content

## Project Structure
```
backend/app/
├── database/
│   └── models.py          # + Prompt model
├── repositories/
│   └── prompt_repository.py # NEW
├── services/
│   └── prompt_service.py    # NEW
├── projects/
│   ├── router.py           # + prompts endpoints
│   └── schema.py           # + Prompt schemas
└── api/
    └── v1/
        └── prompts/        # NEW router
```

## Database Model
```python
class Prompt(Base):
    __tablename__ = "prompts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    project: Mapped["Project"] = relationship("Project", back_populates="prompts")
```

## Code Style
- RTL/Persian UI: تمام پیام‌های خطا به فارسی
- Pydantic schemas با `from_attributes=True`
- Soft Delete: استفاده از `is_active` به جای حذف فیزیکی
- Validation: تمام قوانین در Service Layer

## Testing Strategy
- تست ایجاد Prompt با پروژه معتبر/نامعتبر
- تست محدودیت 10 Prompt فعال
- تست Archive آخرین Prompt فعال
- تست دریافت لیست با/بدون Archive

## Boundaries
- **همیشه:** Validation قبل از هر عملیاتی
- **هرگز:** ویرایش Prompt پس از ایجاد
- **هرگز:** حذف فیزیکی Prompt
- **با سوال:** تغییر ساختار دیتابیس پس از شروع استفاده