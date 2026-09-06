# گزارش روزانه تلگرام (Cloudflare Worker)

هر روز صبح رتبه‌ی برندها برای پرامپت‌های پروژه رو از بک‌اند می‌گیره و به تلگرام ارسال می‌کنه.

## ساختار

- `src/index.js` — ورکر: دریافت گزارش از `/internal/daily-report`، فرمت‌بندی پیام و ارسال به Telegram Bot API
- `wrangler.toml` — تنظیمات + cron روزانه ساعت ۰۸:۰۰ تهران

## ۱. تنظیم بک‌اند

در `backend/.env` یک کلید داخلی بسازید:

```
INTERNAL_API_KEY=<یک رشته تصادفی حداقل ۳۲ کاراکتری>
```

Endpoint جدید: `GET /internal/daily-report?project_id={id}` با هدر `X-API-Key`.

## ۲. ساخت بات تلگرام

1. در تلگرام به [@BotFather](https://t.me/BotFather) پیام بدهید و `/newbot` را بزنید → توکن بات را ذخیره کنید.
2. بات را به گروه/کانال مورد نظر اضافه کنید (یا چت خصوصی شروع کنید).
3. Chat ID را بگیرید: به `https://api.telegram.org/bot<TOKEN>/getUpdates` سر بزنید و `chat.id` را پیدا کنید. برای کانال عمومی می‌توانید خودِ `@channelname` را بگذارید.

## ۳. دیپلوی ورکر

```bash
cd deploy/telegram-worker
npm install -g wrangler
wrangler login
```

در `wrangler.toml` مقادیر `BACKEND_URL` و `PROJECT_ID` را ست کنید، سپس:

```bash
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID
wrangler secret put INTERNAL_API_KEY
wrangler deploy
```

## تست دستی

برای ارسال فوری بدون انتظار برای cron، یک secret دلخواه ست کنید:

```bash
wrangler secret put TRIGGER_SECRET
curl -X POST "https://fanoosai-telegram-report.<subdomain>.workers.dev/send?key=<TRIGGER_SECRET>"
```

## خروجی نمونه

```
📌 بهترین هاست ایران را از کجا بخرم؟
━━━━━━━━━━━━━━

🤖 gpt-5.2
1. hostiran — رتبه 1 | ویزیبلیتی: 3


📌 با ذکر منابع پاسخ بده قوی ترین هاست ایران را از کجا بخرم؟

━━━━━━━━━━━━━━

🤖 gpt-5.2
1. hostiran — رتبه 1 | ویزیبلیتی: 3
2. arvancloud — رتبه 2 | ویزیبلیتی: 7
```

- **رتبه**: جایگاه برند در آخرین اجرای موفق آن پرامپت با آن مدل
- **ویزیبلیتی**: تعداد دفعاتی که برند در اجراهای موفق آن پرامپت+مدل ظاهر شده
