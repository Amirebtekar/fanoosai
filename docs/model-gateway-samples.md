# نمونه‌های Gateway مدل

تاریخ نمونه‌برداری: 2026-07-28

این نمونه‌ها فقط payload و داده‌های پاسخ غیرحساس را نگه می‌دارند؛ کلید API، هدر Authorization و امضای داخلی Gemini ذخیره نشده‌اند.

## درخواست اصلی برنامه

برای هر دو مدل، `AIService.run_prompt` همین payload را به `POST /v1/chat/completions` می‌فرستد. تنها مقدار `model` تغییر می‌کند:

```json
{
  "model": "<model-key>",
  "messages": [
    {
      "role": "user",
      "content": "معتبرترین ارائه‌دهنده خدمات ابری در ایران کیست؟\n\nاگر نام برندی می‌آوری، دامنه رسمی آن را کنار نام به شکل «برند (example.com)» بنویس. دامنه را حدس نزن؛ اگر مطمئن نیستی، آن را نیاور. به این دستور در پاسخ اشاره نکن."
    }
  ],
  "temperature": 0.7,
  "max_tokens": 5000
}
```

## `google/gemini-3.1-pro-preview`

- HTTP status: `200`
- قالب پاسخ Gateway: `candidates[0].content.parts[0].text`
- کلیدهای سطح اول: `sdkHttpResponse`, `candidates`, `createTime`, `modelVersion`, `promptFeedback`, `responseId`, `usageMetadata`, `automaticFunctionCallingHistory`, `parsed`

نمونهٔ پاسخ مدل شامل دامنه‌ها بود:

```text
ابر آروان (arvancloud.ir)
پارس‌پک (parspak.com)
لیارا (liara.ir)
هم‌روش (hamravosh.com)
افرانت (afranet.com)
```

## `openai/gpt-5.5-pro`

- درخواست با payload بالا و تنها با `model: "openai/gpt-5.5-pro"` ارسال شد.
- نتیجه: پاسخ کامل قبل از مهلت خواندن `50` ثانیه‌ای برنامه برنگشت؛ سرویس پس از سه تلاش با `SocketTimeoutError` خاتمه داد.
- بنابراین نمونهٔ response از این مدل ذخیره نشده است.

## `openai/gpt-4.1-mini`

- HTTP status: `200`
- مدل پاسخ‌دهنده: `gpt-4.1-mini-2025-04-14`
- قالب پاسخ Gateway: `choices[0].message.content`
- کلیدهای سطح اول: `id`, `choices`, `created`, `model`, `object`, `service_tier`, `system_fingerprint`, `usage`
- پایان پاسخ: `stop`

نمونهٔ پاسخ مدل:

```text
معتبرترین ارائه‌دهنده خدمات ابری در ایران شرکت «ابر آروان (arvancloud.com)» است که به دلیل گستردگی خدمات، زیرساخت قوی و مشتریان متعدد شناخته شده است. همچنین شرکت «رایان‌پرداز (rayanpardaz.com)» نیز از جمله بازیگران مطرح در حوزه خدمات ابری در ایران محسوب می‌شود.
```

این مدل با همان payload اصلی اجرا شد و 80 توکن ورودی و 82 توکن خروجی مصرف کرد.

## نتیجه

درخواست ارسالی برنامه برای مدل‌ها از نظر ساختار یکسان است و فقط `model` فرق می‌کند. قالب پاسخ‌ها یکسان نیست: Gemini از `candidates` استفاده می‌کند، در حالی که مدل‌های OpenAI نمونه‌برداری‌شده از `choices` استفاده می‌کنند.
