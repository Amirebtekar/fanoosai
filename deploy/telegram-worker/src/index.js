const SEPARATOR = "━━━━━━━━━━━━━━";
const TELEGRAM_LIMIT = 4000;

export function formatReport(data) {
  const blocks = [];
  for (const prompt of data.prompts || []) {
    const lines = [`📌 ${prompt.text}`, SEPARATOR];
    let hasModel = false;
    for (const model of prompt.models || []) {
      if (!model.brands || model.brands.length === 0) continue;
      hasModel = true;
      lines.push("", `🤖 ${model.model_name}`);
      model.brands.forEach((brand, i) => {
        lines.push(`${i + 1}. ${brand.name} — رتبه ${brand.rank} | ویزیبلیتی: ${brand.visibility}`);
      });
    }
    if (hasModel) blocks.push(lines.join("\n"));
  }
  return blocks;
}

async function sendTelegram(env, text) {
  const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text,
      disable_web_page_preview: true,
    }),
  });
  if (!res.ok) {
    throw new Error(`Telegram API ${res.status}: ${await res.text()}`);
  }
}

async function fetchReport(env) {
  const url = `${env.BACKEND_URL.replace(/\/+$/, "")}/internal/daily-report?project_id=${env.PROJECT_ID}`;
  const res = await fetch(url, {
    headers: { "X-API-Key": env.INTERNAL_API_KEY },
  });
  if (!res.ok) {
    throw new Error(`Backend ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runReport(env));
  },
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/send" && request.method === "POST") {
      if (!env.TRIGGER_SECRET || url.searchParams.get("key") !== env.TRIGGER_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }
      ctx.waitUntil(runReport(env));
      return Response.json({ status: "queued" });
    }
    return new Response("ok");
  },
};

async function runReport(env) {
  try {
    const data = await fetchReport(env);
    const blocks = formatReport(data);
    if (blocks.length === 0) {
      console.log("No ranking data to send.");
      return;
    }
    let message = "";
    for (const block of blocks) {
      const candidate = message ? `${message}\n\n\n${block}` : block;
      if (candidate.length > TELEGRAM_LIMIT) {
        await sendTelegram(env, message);
        message = block;
      } else {
        message = candidate;
      }
    }
    if (message) await sendTelegram(env, message);
  } catch (err) {
    console.error("Report failed:", err.message);
  }
}
