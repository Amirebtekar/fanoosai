# FanoosAI Backend

API سرور FastAPI برای پروژه FanoosAI با پشتیبانی از احراز هویت دوگانه (ایمیل/رمز عبور و شماره موبایل/OTP).

## ساختار پروژه

```
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # نقطه ورود برنامه
│   ├── core/
│   │   └── config.py           # تنظیمات برنامه
│   │
│   ├── database/
│   │   ├── connection.py       # اتصال به دیتابیس PostgreSQL
│   │   └── models.py           # تعریف مدل‌های SQLAlchemy
│   │
│   ├── users/
│   │   ├── model.py            # مدل‌های Pydantic کاربر
│   │   ├── schema.py           # اسکیماهای ورودی/خروجی
│   │   ├── router.py           # مسیرهای API کاربر
│   │   └── service.py          # لایه سرویس کاربران
│   │
│   ├── auth/
│   │   ├── jwt.py              # استراتژی JWT برای احراز هویت
│   │   ├── password.py         # هش کردن رمز عبور با bcrypt
│   │   └── sms_service.py      # سرویس ارسال OTP از طریق Melipayamak
│   │
│   └── migrations/             # مهاجرت‌های دیتابیس
│
└── .env                        # فایل تنظیمات محیطی
```

## پیش‌نیازها

- Python 3.11+
- PostgreSQL با driver `asyncpg`
- حساب کاربری در سرویس پیامک Melipayamak (Parspack)

## نصب وابستگی‌ها

```bash
pip install fastapi uvicorn[standard] fastapi-users[sqlalchemy] bcrypt passlib[bcrypt] pydantic-settings aiohttp asyncpg python-dotenv
```

## پیکربندی

1. فایل `.env` را با مقادیر زیر پر کنید:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost/fanoosai
JWT_SECRET_KEY=your-super-secret-jwt-key-change-me
MELIPAYAMAK_USERNAME=your-username
MELIPAYAMAK_PASSWORD=your-password
MELIPAYAMAK_FROM_NUMBER=+985000123456
```

2. دیتابیس PostgreSQL ایجاد کنید:

```bash
createdb fanoosai
```

## اجرا

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### احراز هویت کاربر
- `POST /auth/register` - ثبت‌نام کاربر جدید
- `POST /auth/login` - ورود با ایمیل/رمز عبور
- `POST /auth/send-otp` - ارسال کد OTP به شماره موبایل
- `POST /auth/verify-otp` - تأیید کد OTP
- `GET /auth/jwt/login` - لایه‌ی FastAPI Users JWT

### کاربران
- `GET /users/me` - دریافت اطلاعات کاربر فعلی
- `PUT /users/me` - به‌روزرسانی اطلاعات کاربر

## ساختار دیتابیس

جدول `users` با فیلدهای زیر:
- `id` - شناسه یکتا (کلید اصلی)
- `email` - ایمیل کاربر (یکتا)
- `phone` - شماره موبایل کاربر (یکتا)
- `hashed_password` - رمز عبور هش‌شده
- `is_active` - وضعیت فعال/غیرفعال
- `is_verified` - وضعیت تأیید شماره موبایل
- `is_superuser` - وضعیت کاربر مدیر

## نکات فنی

- از SQLAlchemy ORM با driver asyncpg استفاده می‌شود
- تمام درخواست‌ها به صورت async پیاده‌سازی شده‌اند
- JWT توکن با مدت زمان تنظیم‌شده در متغیر `JWT_LIFETIME_SECONDS`
- OTP کدهای تصادفی ۶ رقمی برای تأیید شماره موبایل ارسال می‌شوند

## مستندات بیشتر

برای مستندات کامل FastAPI Users:
- https://fastapi-users.github.io/fastapi-users/

برای مستندات FastAPI:
- https://fastapi.tiangolo.com/