import type { PromptLeaderItem } from '@/lib/api'

export const PROMPT_LEADERS_EXPLANATION = 'نفر اول هر پرامپت برندی است که بهترین میانگین رتبه را دارد، از میان برندهایی که دست‌کم در ۲۰٪ پاسخ‌های آن پرامپت آمده‌اند.'
export const OWN_BRAND_MISSING_HINT = 'برند خود را در تنظیمات پروژه تعریف کنید.'

export function splitPromptLeaders(items: PromptLeaderItem[]) {
  return {
    behind: items.filter(item => !item.own_is_leader),
    leading: items.filter(item => item.own_is_leader),
  }
}

export function formatRank(value: number, locale = 'fa-IR'): string {
  return value.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function appearancesLabel(appearances: number, total: number, locale = 'fa-IR'): string {
  return `${appearances.toLocaleString(locale)} از ${total.toLocaleString(locale)} پاسخ`
}

export function ownStatusLabel(item: PromptLeaderItem, locale = 'fa-IR'): string {
  const own = item.own
  if (!own) return 'در پاسخ‌ها دیده نشده‌اید'
  if (!own.eligible || own.position == null) return `کم دیده شده‌اید (${appearancesLabel(own.appearances, item.total_runs, locale)})`
  return `رتبه ${own.position.toLocaleString(locale)} از برندهای پرتکرار`
}
