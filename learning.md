# راهنمای یادگیری بک‌اند FanoosAI

این راهنما نقشه‌ی فایل‌های بک‌اند است، نه جایگزین خواندن کد. برای یادگیری عملی، از `app/main.py` شروع کنید، سپس یک مسیر کامل مانند «ساخت پروژه» یا «اجرای Prompt» را تا router، service، repository و model دنبال کنید.

## نقشه‌ی کلی

```text
HTTP request → router → service → repository → SQLAlchemy model → PostgreSQL
                         ↓
                    AI Gateway / Redis / SMS provider

scheduler → Redis Stream → worker → AIRunService → AI Gateway → brand extraction
```

- **Router**: قرارداد HTTP، اعتبارسنجی ورودی و پاسخ/کد خطا را نگه می‌دارد.
- **Service**: منطق کسب‌وکار را نگه می‌دارد؛ مثلاً اجرای مدل یا قوانین OTP.
- **Repository**: خواندن و نوشتن داده با SQLAlchemy را متمرکز می‌کند.
- **Model**: تعریف جدول‌ها، ستون‌ها و رابطه‌های پایگاه‌داده است.
- **Schema**: مدل‌های Pydantic برای شکل داده‌ی ورودی و خروجی API هستند.

## پیکربندی و راه‌اندازی

### `backend/pyproject.toml`

تعریف بسته‌ی پایتون، نسخه‌ی لازم پایتون و وابستگی‌های بک‌اند است؛ ابزارهایی مانند FastAPI، SQLAlchemy، Redis و pytest از اینجا مشخص می‌شوند.

### `backend/alembic.ini`

فایل پیکربندی Alembic است؛ Alembic ابزار مدیریت migration پایگاه‌داده است و این فایل تنظیمات اتصال، مسیر migrationها و لاگ آن را نگه می‌دارد.

### `backend/.gitignore`

فایل‌ها و پوشه‌های محلی مانند محیط مجازی، کش تست و فایل‌های حساس را از Git خارج می‌کند تا ناخواسته وارد مخزن نشوند.

### `backend/app/__init__.py`

این فایل خالی است و فقط `app` را به یک package پایتون تبدیل می‌کند؛ منطق اجرایی ندارد.

### `backend/app/main.py`

نقطه‌ی ورود API است: برنامه‌ی FastAPI را می‌سازد، lifecycle اتصال‌های Redis و دیتابیس را می‌بندد، CORS و headerهای امنیتی را اضافه می‌کند، health/metrics endpointها را می‌سازد و همه‌ی routerها را به برنامه وصل می‌کند.

### `backend/app/dependencies.py`

dependency مشترک FastAPI برای ساختن یک `AsyncSession` دیتابیس در هر درخواست است؛ routerها با `Depends(get_session)` آن را دریافت می‌کنند.

### `backend/app/observability.py`

متریک‌های Prometheus برای درخواست‌های HTTP، تماس‌های AI و صف را تعریف می‌کند و لاگ‌ها را به JSON ساخت‌یافته با شناسه‌ی درخواست تبدیل می‌کند.

### `backend/app/retention.py`

تابع `archive_old_runs` را دارد که با یک تابع SQL، اجراهای AI قدیمی‌تر از مدت نگه‌داری تنظیم‌شده را آرشیو می‌کند؛ بخش `__main__` اجازه می‌دهد مستقل اجرا شود.

### `backend/app/scheduler.py`

زمان‌بند کارهای روزانه است: Promptهای فعال و مدل‌های فعالشان را می‌خواند، اجراهای آرشیوشده‌ی قدیمی را پاک‌سازی می‌کند و برای هر prompt/model یک job یکتا در Redis Stream قرار می‌دهد.

### `backend/app/worker.py`

مصرف‌کننده‌ی صف Redis است؛ job را می‌خواند، Prompt و مدل را بارگذاری می‌کند، `AIRunService` را اجرا می‌کند و در خطا با سقف retry دوباره صف‌بندی یا شکست را ثبت می‌کند.

### `backend/app/organizations_router.py`

endpointهای ساخت سازمان و افزودن/تغییر عضو را ارائه می‌کند؛ نقش‌های `owner`، `admin`، `analyst` و `viewer` را بررسی می‌کند و فقط owner/admin را مجاز به مدیریت اعضا می‌داند.

## core و database

### `backend/app/core/__init__.py`

فایل خالیِ package برای ماژول‌های هسته است و منطق ندارد.

### `backend/app/core/config.py`

کلاس `Settings` متغیرهای محیطی را از `.env` می‌خواند: اتصال دیتابیس، JWT، CORS، AI Gateway، Redis، OTP و تنظیمات pool. همچنین کوتاه یا پیش‌فرض بودن راز JWT را رد می‌کند.

### `backend/app/database/__init__.py`

فایل marker برای package دیتابیس است و منطق ندارد.

### `backend/app/database/connection.py`

engine async SQLAlchemy، factory ساخت session و کلاس پایه‌ی ORM (`Base`) را تعریف می‌کند؛ تمام modelها از این `Base` ارث می‌برند.

### `backend/app/database/models.py`

مدل‌های SQLAlchemy و در نتیجه schema پایگاه‌داده را تعریف می‌کند: کاربر، سازمان/عضویت، پروژه، Prompt، مدل AI، اتصال Prompt-Model، اجرای AI، claim روزانه، برند و رتبه‌بندی، هشدار و لینک اشتراک گزارش. رابطه‌ها و unique constraintها در همین فایل، یکپارچگی داده را تضمین می‌کنند؛ `get_user_db` نیز adapter موردنیاز fastapi-users را می‌سازد.

## احراز هویت و کاربران

### `backend/app/auth/__init__.py`

فایل خالیِ package احراز هویت است و منطق ندارد.

### `backend/app/auth/fastapi_users.py`

کتابخانه‌ی `fastapi-users` را برای مدل کاربر این پروژه تنظیم می‌کند و backend احراز هویت JWT را با cookie امن، HttpOnly و SameSite ایجاد می‌کند.

### `backend/app/auth/jwt.py`

strategy ساخت و اعتبارسنجی JWT را با secret و طول عمر تعریف‌شده در تنظیمات می‌سازد.

### `backend/app/auth/password.py`

دو تابع کوچک برای hash و بررسی گذرواژه با bcrypt فراهم می‌کند؛ در جریان OTP برای رمز داخلیِ کاربر تازه‌ثبت‌نام‌شده استفاده می‌شود.

### `backend/app/auth/router.py`

API احراز هویت با OTP را تعریف می‌کند: ثبت‌نام، درخواست کد، تأیید کد و `/auth/me`. شماره‌ی موبایل ایران و کد شش‌رقمی را با Pydantic اعتبارسنجی می‌کند و پس از تأیید cookie JWT می‌گذارد.

### `backend/app/auth/sms_service.py`

client سرویس Melipayamak است که OTP را با timeout ارسال می‌کند؛ پاسخ provider را با دقت parse می‌کند و فقط شناسه‌ی عددی مثبت را موفقیت می‌داند.

### `backend/app/users/__init__.py`

فایل marker برای package کاربران است و منطق ندارد.

### `backend/app/users/manager.py`

پیاده‌سازی `UserManager` برای fastapi-users است؛ secretهای token بازیابی/تأیید را تعیین می‌کند و رویدادهای ثبت‌نام، بازیابی رمز و تأیید ایمیل را log می‌کند.

### `backend/app/users/schema.py`

schemaهای Pydantic مربوط به کاربر را تعریف می‌کند: داده‌ی امن قابل‌نمایش (`UserRead`) و ورودی ساخت/به‌روزرسانی کاربر با email و phone.

### `backend/app/services/auth_service.py`

منطق کامل ورود با OTP را نگه می‌دارد: تولید کد امن، ذخیره و محدودسازی نرخ در Redis، سقف تلاش ناموفق، fallback فقط در حالت DEBUG و ثبت‌نام یا تأیید کاربر.

### `backend/app/repositories/user_repository.py`

دسترسی دیتابیس کاربر را متمرکز می‌کند: یافتن با شماره یا شناسه، ساخت کاربر و علامت‌گذاری کاربر به‌عنوان تأییدشده.

## پروژه و Prompt

### `backend/app/projects/__init__.py`

فایل marker برای package پروژه‌ها است و منطق ندارد.

### `backend/app/projects/schema.py`

مدل‌های Pydantic پروژه و Prompt را تعریف می‌کند؛ ورودی ساخت/ویرایش پروژه، برند پروژه، ورودی Prompt و پاسخ‌های API در این فایل شکل می‌گیرند.

### `backend/app/projects/router.py`

API CRUD پروژه، برندهای یک پروژه، ruleهای هشدار و خواندن هشدارها را ارائه می‌کند. دسترسی بر پایه‌ی نقش سازمان بررسی می‌شود و پاسخ‌ها به schemaهای پروژه تبدیل می‌شوند.

### `backend/app/projects/prompt_router.py`

API Promptهای یک پروژه است: ساخت، فهرست، archive/restore، اتصال یا حذف مدل AI، اجرای دستی و مشاهده‌ی تاریخچه/وضعیت اجرای هر مدل. این فایل قبل از عملیات، مالکیت یا نقش نوشتن پروژه را کنترل می‌کند.

### `backend/app/projects/ai_models_router.py`

API مدل‌های AI را فراهم می‌کند: فهرست مدل‌های فعال، ساخت مدل و همگام‌سازی فهرست مدل‌ها با AI Gateway؛ endpointها برای کاربر احراز هویت‌شده هستند.

### `backend/app/projects/ai_models_schema.py`

schema پاسخ مدل AI را تعریف می‌کند تا فقط فیلدهای مورد نیاز مانند شناسه، نام، provider، کلید مدل و فعال‌بودن به client ارسال شود.

### `backend/app/projects/ai_runs_schema.py`

schemaهای نتیجه‌ی اجرای AI و قابلیت اجرای هر مدل برای یک Prompt را تعریف می‌کند؛ client از آن می‌فهمد اجرا موفق بوده، چند برند پیدا شده و آیا اجرای امروز قبلاً claim شده است یا نه.

### `backend/app/services/project_service.py`

قوانین کسب‌وکار پروژه را روی repository می‌گذارد: بررسی کاربر، جلوگیری از URL تکراری و فراخوانی عملیات ساخت، فهرست، خواندن، ویرایش و حذف پروژه.

### `backend/app/services/prompt_service.py`

قواعد Prompt را نگه می‌دارد: وجود پروژه، جلوگیری از متن تکراری، معتبر/فعال بودن مدل‌های انتخابی و سقف Prompt فعال؛ همچنین archive و restore را با این سقف کنترل می‌کند.

### `backend/app/repositories/project_repository.py`

Queryهای پروژه را دارد: ساخت سازمان شخصی در صورت نیاز، ساخت پروژه و برند owned اولیه، خواندن و شمارش Prompt/مدل، و بررسی نقش‌های read/write/manage در سازمان.

### `backend/app/repositories/prompt_repository.py`

Queryهای Prompt و اتصال آن به مدل‌ها را انجام می‌دهد: ساخت، eager-loading مدل‌ها، افزودن/حذف مدل، فیلتر archive و پاک‌سازی کامل Promptهای آرشیوشده‌ی قدیمی به همراه داده‌های وابسته.

## AI، برند و صف

### `backend/app/services/ai_model_service.py`

مدل‌های قابل استفاده را از repository می‌خواند یا endpoint `/v1/models` در AI Gateway را می‌گیرد، پاسخ‌های احتمالی gateway را normalise می‌کند و نتیجه را همگام می‌سازد.

### `backend/app/services/ai_service.py`

client مشترک AI Gateway است؛ یک session HTTP قابل استفاده‌مجدد می‌سازد، درخواست chat completion را با retry برای خطاهای موقت می‌فرستد و متریک موفقیت/مدت اجرا را ثبت می‌کند.

### `backend/app/services/ai_run_service.py`

orchestrator اجرای Prompt است: برای هر مدل claim روزانه می‌گیرد، prompt را به AI می‌فرستد، نتیجه یا خطا را ذخیره می‌کند، برندها را استخراج و ذخیره می‌کند و هشدارهای مرتبط را ایجاد می‌کند.

### `backend/app/services/brand_extraction_service.py`

یک درخواست دوم با JSON Schema به مدل AI می‌فرستد تا برندها، رتبه، domain و confidence را از پاسخ اصلی استخراج کند؛ سپس JSON را parse و داده‌های ناسازگار مانند domain نامعتبر یا rank نامعتبر را رد می‌کند.

### `backend/app/services/brand_persistence_service.py`

برندهای استخراج‌شده را با domain یا نام نرمال‌شده تطبیق می‌دهد، در صورت نیاز Brand تازه می‌سازد و associationهای `RunBrand` را با rank و confidence ذخیره می‌کند؛ شمارش جدید و قبلی بودن برندها را برمی‌گرداند.

### `backend/app/repositories/ai_model_repository.py`

عملیات دیتابیس مدل AI را انجام می‌دهد: لیست مدل فعال، یافتن/ساخت مدل و sync با gateway؛ مدل‌هایی که دیگر در gateway نیستند را غیرفعال می‌کند.

### `backend/app/repositories/ai_run_repository.py`

ذخیره‌ی اجرای AI، claim اتمی اجرای روزانه و تاریخچه‌ی اجرا را انجام می‌دهد. همچنین ruleهای هشدار برای خطای اجرا، رقیب جدید، افت رتبه و ناپدیدشدن برند را با cooldown اعمال می‌کند.

### `backend/app/infrastructure/__init__.py`

فایل marker برای زیرساخت‌های خارجی است و منطق ندارد.

### `backend/app/infrastructure/redis_client.py`

یک client async و lazy برای Redis می‌سازد و lifecycle آن را مدیریت می‌کند؛ healthcheck به صورت امن `ping` می‌زند و خطا را به `False` تبدیل می‌کند.

### `backend/app/infrastructure/run_queue.py`

قرارداد job صف (`PromptRunJob`) و wrapper Redis Stream را دارد: ساخت consumer group، deduplication اجرای روزانه با Lua، lock زمان‌بند، retry، reclaim jobهای مانده و acknowledge کردن jobهای کامل‌شده.

## تحلیل و گزارش

### `backend/app/analytics/schema.py`

schemaهای پاسخ تحلیل را تعریف می‌کند: خلاصه dashboard، تاریخچه‌ی Prompt و برند، رتبه‌ی آخر، روند برند، جزئیات برند، اجرای اخیر و صفحه‌بندی.

### `backend/app/analytics/router.py`

endpointهای تحلیل اصلی را دارد: dashboard پروژه، تحلیل Prompt، تاریخچه‌ی برند/Prompt/پروژه، رتبه‌های آخر و روند برند. Queryها با فیلتر پروژه، Prompt، مدل و بازه‌ی زمان کار می‌کنند و دسترسی سازمان را بررسی می‌کنند.

### `backend/app/analytics/extra_router.py`

Brand details are implemented only in `backend/app/analytics/router.py`; this module owns run export and report sharing.

endpointهای تحلیل تکمیلی را دارد: صفحه‌بندی اجراهای پروژه، خروجی CSV، ساخت/لغو لینک اشتراک زمان‌دار، گزارش عمومی با token و جزئیات یک برند؛ همه به جز گزارش public، مالکیت پروژه/برند را کنترل می‌کنند.

## migrationهای قدیمی

### Removed: `backend/migrations_old/001_create_brands_and_run_brands.sql`

SQL migration قدیمی برای ساخت جدول‌های `brands` و `run_brands` و index/constraintهای آن‌ها است؛ این فایل نشان می‌دهد برندها چگونه به یک اجرای AI متصل می‌شوند.

### Removed: `backend/migrations_old/versions/20250308_add_ai_run_extraction_fields.py`

migration قدیمی Alembic است که فیلدهای وضعیت/خطای استخراج برند را به جدول اجرای AI اضافه یا در downgrade حذف می‌کند.

## تست‌ها

### `backend/tests/test_ai_models.py`

رفتار API و service مدل‌های AI را پوشش می‌دهد، به‌ویژه normalise کردن پاسخ gateway و همگام‌سازی مدل‌ها.

### `backend/tests/test_ai_runs.py`

مسیر اجرای Prompt با مدل AI را بررسی می‌کند؛ از جمله ذخیره‌ی نتیجه و جلوگیری از اجرای تکراری روزانه.

### `backend/tests/test_archived_prompt_purge.py`

بررسی می‌کند پاک‌سازی Prompt آرشیوشده، داده‌های وابسته مانند run، brand link، مدل و claim روزانه را نیز حذف می‌کند.

### `backend/tests/test_brand_extraction_service.py`

parser استخراج برند را با پاسخ‌های معتبر و نامعتبر آزمایش می‌کند تا فقط JSON قراردادی با rank، name، domain و confidence پذیرفته شود.

### `backend/tests/test_brand_persistence_service.py`

منطق ذخیره/تطبیق برندها و شمارش برندهای جدید یا قبلاً موجود را آزمایش می‌کند.

### `backend/tests/test_critical_security.py`

کنترل‌های امنیتی مهم مانند تنظیم cookie/JWT، محدودسازی OTP یا headerهای امنیتی را در سطح رفتار قابل مشاهده بررسی می‌کند.

### `backend/tests/test_daily_prompt_execution.py`

سناریوهای اجرای روزانه، claim شدن اجرا بین manual و scheduled و کار زمان‌بند/worker را پوشش می‌دهد.

### `backend/tests/test_high_security.py`

سناریوهای امنیتی سطح بالاتر، به‌خصوص رفتار در نبود Redis یا محدودیت‌های OTP، را بررسی می‌کند.

### `backend/tests/test_history_api.py`

endpointهای تاریخچه و تحلیل را آزمایش می‌کند تا داده و صفحه‌بندی اجرای Prompt/برند درست بازگردد.

### `backend/tests/test_openapi_httpbearer.py`

ساخت schema OpenAPI مربوط به authentication را بررسی می‌کند تا clientها روش امنیت API را درست بشناسند.

### `backend/tests/test_organization_migration.py`

تغییرات مربوط به سازمان و اتصال پروژه‌ها به سازمان را از دید migration یا مدل داده بررسی می‌کند.

### `backend/tests/test_organization_roles.py`

سطوح دسترسی owner/admin/analyst/viewer را در عملیات سازمان و پروژه آزمایش می‌کند.

### `backend/tests/test_project_counts_query.py`

Query فهرست پروژه را بررسی می‌کند تا تعداد Promptهای فعال و تعداد اتصال مدل‌ها درست محاسبه شوند.

### `backend/tests/test_project_counts_schema.py`

schema پاسخ پروژه را برای وجود و نوع شمارش Prompt و مدل بررسی می‌کند.

### `backend/tests/test_project_creation.py`

مسیر ساخت پروژه، برند owned اولیه، سازمان شخصی و خطاهای تکراری بودن URL را پوشش می‌دهد.

### `backend/tests/test_project_settings.py`

اعتبارسنجی یا رفتار تنظیمات پروژه را در سطح حداقلی بررسی می‌کند.

### `backend/tests/test_project_update_refresh.py`

بررسی می‌کند پس از ویرایش پروژه، داده‌ی refresh‌شده با مقادیر جدید به API بازگردد.

### `backend/tests/test_project_update_schema.py`

schema ورودی update پروژه را بررسی می‌کند تا فیلدهای قابل‌ویرایش قرارداد صحیحی داشته باشند.

### `backend/tests/test_project_website_url.py`

قواعد URL وب‌سایت پروژه، از جمله یکتا بودن یا اعتبارسنجی آن را پوشش می‌دهد.

### `backend/tests/test_prompt_schema.py`

schema ساخت Prompt و محدودیت‌های متن و شناسه‌های مدل را آزمایش می‌کند.

## چه چیزهایی عمداً فهرست نشده‌اند؟

`backend/.venv/` و `backend/.pytest_cache/` خروجی محیط محلی هستند، نه کد پروژه. `uv.lock` نیز فایل تولیدشده‌ی قفل وابستگی است و برای یادگیری منطق برنامه لازم نیست. فایل `.env` عمداً توضیح داده نشده، چون محل نگه‌داری رازهاست؛ برای نام و معنای متغیرهای آن، `app/core/config.py` و `templates/env.example` را بخوانید.

## مسیر پیشنهادی مطالعه

1. `app/main.py` و `app/core/config.py` را بخوانید تا برنامه و تنظیمات را ببینید.
2. `database/models.py` را کنار `repositories/project_repository.py` بخوانید تا رابطه‌ی داده و query را وصل کنید.
3. `projects/router.py` → `services/project_service.py` → repository را برای یک درخواست ساده دنبال کنید.
4. `projects/prompt_router.py` → `services/ai_run_service.py` → `worker.py` را برای جریان اصلی محصول دنبال کنید.
5. در پایان `analytics/router.py` را بخوانید؛ queryهای آن بهترین نمونه برای فهم SQLAlchemy و داده‌های ذخیره‌شده هستند.
