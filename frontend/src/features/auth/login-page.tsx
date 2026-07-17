import { useState, useRef, useCallback } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/auth-store'
import { requestSms, verifySms, getErrorMessage } from '@/lib/api'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) { return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d]) }
const PHONE_REGEX = /^09[0-9]{9}$/

export function LoginPage() {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()
  const [step, setStep] = useState<'phone' | 'otp'>('phone')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [phoneErrors, setPhoneErrors] = useState<string[]>([])
  const otpRefs = useRef<(HTMLInputElement | null)[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const clearAlerts = () => { setError(''); setSuccess('') }
  const startCountdown = useCallback(() => { setCountdown(120); clearInterval(timerRef.current); timerRef.current = setInterval(() => { setCountdown(prev => { if (prev <= 1) { clearInterval(timerRef.current); return 0 } return prev - 1 }) }, 1000) }, [])

  const handleSendOtp = async () => {
    clearAlerts(); const errs: string[] = []
    if (!phone) errs.push('phone'); else if (!PHONE_REGEX.test(phone)) errs.push('phone')
    setPhoneErrors(errs); if (errs.length) return
    setLoading(true)
    try { await requestSms({ phone }); setStep('otp'); startCountdown(); setSuccess(`کد تایید به شماره ${toPersianDigits(phone.slice(0, 4))}****${toPersianDigits(phone.slice(-2))} ارسال شد`); setTimeout(() => otpRefs.current[0]?.focus(), 100) }
    catch (e) { setError(getErrorMessage(e, 'خطا در ارسال کد تایید')) }
    finally { setLoading(false) }
  }

  const handleOtpChange = (idx: number, value: string) => { const digit = value.replace(/[^0-9]/g, '').slice(-1); setOtp(prev => { const n = [...prev]; n[idx] = digit; return n }); if (digit && idx < 5) otpRefs.current[idx + 1]?.focus() }
  const handleOtpKeyDown = (idx: number, e: React.KeyboardEvent) => { if (e.key === 'Backspace' && !otp[idx] && idx > 0) { setOtp(prev => { const n = [...prev]; n[idx - 1] = ''; return n }); otpRefs.current[idx - 1]?.focus() } }
  const handleOtpPaste = (e: React.ClipboardEvent) => { e.preventDefault(); const paste = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6); setOtp(paste.split('').concat(Array(6 - paste.length).fill('')).slice(0, 6)); if (paste.length === 6) otpRefs.current[5]?.focus(); else if (paste.length > 0) otpRefs.current[paste.length]?.focus() }

  const handleVerifyOtp = async () => {
    clearAlerts(); const code = otp.join(''); if (code.length !== 6) return
    setLoading(true)
    try { const res = await verifySms({ phone, code }); if (res.access_token) setToken(res.access_token); if (res.user) setUser(res.user); setSuccess('ورود با موفقیت انجام شد!'); setTimeout(() => navigate({ to: '/dashboard' }), 1200) }
    catch (e) { setError(getErrorMessage(e, 'کد وارد شده صحیح نیست')) }
    finally { setLoading(false) }
  }

  const handleResend = async () => { clearAlerts(); setLoading(true); try { await requestSms({ phone }); setSuccess('کد تایید مجدداً ارسال شد'); startCountdown(); setOtp(['', '', '', '', '', '']); otpRefs.current[0]?.focus() } catch (e) { setError(getErrorMessage(e, 'خطا در ارسال مجدد کد')) } finally { setLoading(false) } }
  const backToPhone = () => { setStep('phone'); setOtp(['', '', '', '', '', '']); clearAlerts(); clearInterval(timerRef.current); setCountdown(0); setPhoneErrors([]) }

  return (
    <div className="flex flex-col min-h-screen bg-bg text-fg font-vazirmatn" dir="rtl">
      <main className="flex-1 flex flex-col items-center justify-center px-5 py-10">
        <div className="w-full max-w-[420px]">
          <div className="flex items-center gap-2.5 mb-2 justify-center"><span className="w-[10px] h-[10px] bg-accent-neon border-2 border-border" /><span className="text-2xl font-black tracking-tight">FanoosAI</span></div>
          <h1 className="text-[1.6rem] font-black mb-1.5">ورود به حساب</h1>
          <p className="text-muted-text font-medium text-sm mb-7">شماره موبایل خود را وارد کنید تا کد تایید برایتان ارسال شود</p>
          {(error || success) && <div className={`mb-4 p-3 border-3 border-border text-sm font-bold ${error ? 'bg-red-950/50 border-red-800' : 'bg-green-950/50 border-green-800'}`} role={error ? 'alert' : 'status'}>{error || success}</div>}
          {step === 'phone' && <div><div className="mb-4"><label className="block font-bold text-sm mb-2" htmlFor="phone-input">شماره موبایل</label><input id="phone-input" type="tel" className="w-full p-3 border-3 border-border font-vazirmatn outline-none" placeholder="09123456789" dir="ltr" inputMode="numeric" maxLength={11} autoComplete="tel" value={phone} onChange={e => { setPhone(e.target.value.replace(/[^0-9]/g, '')); setPhoneErrors([]) }} />{phoneErrors.includes('phone') && <p className="text-sm text-red-600 mt-1 font-bold">شماره موبایل صحیح وارد کنید</p>}</div><button type="button" disabled={loading} className="w-full p-3 font-extrabold border-3 border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] disabled:opacity-50 font-vazirmatn" onClick={handleSendOtp}>{loading ? 'در حال پردازش...' : 'ارسال کد تایید'}</button></div>}
          {step === 'otp' && <div><div className="mb-4"><label className="block font-bold text-sm mb-2">کد ۶ رقمی را وارد کنید</label><div className="flex gap-2 justify-center" dir="ltr" onPaste={handleOtpPaste}>{otp.map((digit, idx) => (<input key={idx} ref={el => { otpRefs.current[idx] = el }} type="tel" className="w-12 h-12 text-center border-3 border-border font-bold text-lg outline-none font-vazirmatn" maxLength={1} inputMode="numeric" pattern="[0-9]" aria-label={`رقم ${idx + 1}`} value={digit} onChange={e => handleOtpChange(idx, e.target.value)} onKeyDown={e => handleOtpKeyDown(idx, e)} autoFocus={idx === 0} />))}</div></div><div className="text-center text-sm text-muted-text mb-4">{countdown > 0 ? <><span className="font-bold">{toPersianDigits(Math.floor(countdown / 60) < 10 ? '0' + Math.floor(countdown / 60) : Math.floor(countdown / 60))}:{toPersianDigits(countdown % 60 < 10 ? '0' + (countdown % 60) : countdown % 60)}</span> تا ارسال مجدد</> : <span className="font-bold">۰۰:۰۰</span>}</div>{countdown === 0 && <button type="button" onClick={handleResend} className="bg-none border-none text-fg font-extrabold text-sm underline underline-offset-3 cursor-pointer mx-auto block mb-5 font-vazirmatn">ارسال مجدد کد</button>}<button type="button" disabled={loading || otp.join('').length !== 6} className="w-full p-3 font-extrabold border-3 border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] disabled:opacity-50 font-vazirmatn" onClick={handleVerifyOtp}>{loading ? 'در حال پردازش...' : 'تایید و ورود'}</button><button type="button" onClick={backToPhone} className="w-full mt-3 p-3 font-bold border-3 border-border bg-card text-fg font-vazirmatn cursor-pointer">تغییر شماره</button></div>}
          <div className="text-center mt-7 font-semibold text-sm text-muted-text">حساب کاربری ندارید؟ <Link to="/register" className="font-extrabold text-fg underline underline-offset-3">ثبت‌نام کنید</Link></div>
        </div>
      </main>
    </div>
  )
}
