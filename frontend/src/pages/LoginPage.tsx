import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) {
  return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d])
}

const PHONE_REGEX = /^09[0-9]{9}$/

export default function LoginPage() {
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

  const phoneValid = PHONE_REGEX.test(phone)

  const clearAlerts = () => { setError(''); setSuccess('') }

  const startCountdown = useCallback(() => {
    setCountdown(120)
    clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [])

  const handleSendOtp = async () => {
    clearAlerts()
    const errs: string[] = []
    if (!phone) errs.push('phone')
    else if (!PHONE_REGEX.test(phone)) errs.push('phone')
    setPhoneErrors(errs)
    if (errs.length) return

    setLoading(true)
    // Simulate API call
    await new Promise(r => setTimeout(r, 1500))
    setLoading(false)

    setStep('otp')
    startCountdown()
    setSuccess(`کد تایید به شماره ${toPersianDigits(phone.slice(0, 4))}****${toPersianDigits(phone.slice(-2))} ارسال شد`)
    setTimeout(() => otpRefs.current[0]?.focus(), 100)
  }

  const handleOtpChange = (idx: number, value: string) => {
    const digit = value.replace(/[^0-9]/g, '').slice(-1)
    setOtp(prev => {
      const next = [...prev]
      next[idx] = digit
      return next
    })
    if (digit && idx < 5) {
      otpRefs.current[idx + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      setOtp(prev => { const n = [...prev]; n[idx - 1] = ''; return n })
      otpRefs.current[idx - 1]?.focus()
    }
  }

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const paste = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6)
    setOtp(paste.split('').concat(Array(6 - paste.length).fill('')).slice(0, 6))
    if (paste.length === 6) {
      otpRefs.current[5]?.focus()
    } else if (paste.length > 0) {
      otpRefs.current[paste.length]?.focus()
    }
  }

  const handleVerifyOtp = async () => {
    clearAlerts()
    const code = otp.join('')
    if (code.length !== 6) return

    setLoading(true)
    // Simulate API call
    await new Promise(r => setTimeout(r, 1500))
    setLoading(false)

    setSuccess('ورود با موفقیت انجام شد!')
    // navigate to dashboard after delay
  }

  const handleResend = () => {
    clearAlerts()
    setSuccess('کد تایید مجدداً ارسال شد')
    startCountdown()
    setOtp(['', '', '', '', '', ''])
    otpRefs.current[0]?.focus()
  }

  const backToPhone = () => {
    setStep('phone')
    setOtp(['', '', '', '', '', ''])
    clearAlerts()
    clearInterval(timerRef.current)
    setCountdown(0)
    setPhoneErrors([])
  }

  return (
    <div className="flex flex-col min-h-screen lg:flex-row">
      {/* Desktop brand panel */}
      <aside
        className="hidden lg:flex lg:w-[46%] bg-surface border-r-[3px] border-border items-center justify-center relative overflow-hidden"
        aria-hidden="true"
      >
        <div className="relative w-full h-full flex items-center justify-center p-12">
          <div
            className="w-full max-w-[520px] aspect-[4/3] bg-gradient-to-br from-[#B8F0D8] via-[#A8DFF0] to-[#D4C5F9] border-[3px] border-border shadow-[6px_6px_0_#1A1A1A] flex flex-col items-center justify-center p-10 text-center"
            role="img"
            aria-label="پلتفرم مدیریت پرامپت"
          >
            <span className="text-5xl mb-4">🧠</span>
            <span className="text-lg font-bold text-muted">مدیریت هوشمند پرامپت‌ها</span>
          </div>
          <div className="absolute bottom-8 left-8 w-[50px] h-[50px] border-b-[3px] border-l-[3px] border-border" aria-hidden="true" />
          <div className="absolute top-8 right-8 w-[50px] h-[50px] border-t-[3px] border-r-[3px] border-border" aria-hidden="true" />
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex flex-col items-center justify-center px-5 py-10 lg:py-16 lg:px-16" role="main">
        <div className="w-full max-w-[420px]">
          {/* Mobile brand */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-2" aria-hidden="true">
            <span className="w-[10px] h-[10px] bg-accent-neon border-2 border-border" />
            <span className="text-2xl font-black tracking-tight">مدیریت پرامپت</span>
          </div>
          <p className="lg:hidden text-center text-muted font-semibold text-sm mb-8">
            سامانه مدیریت پرامپت
          </p>

          <h1 className="text-2xl font-black mb-1">ورود به حساب</h1>
          <p className="text-muted font-medium text-sm mb-7">
            شماره موبایل خود را وارد کنید تا کد تایید برایتان ارسال شود
          </p>

          {/* Alerts */}
          <div className={`alert ${error ? 'alert-error visible' : ''}`} role="alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{error}</span>
          </div>
          <div className={`alert ${success ? 'alert-success visible' : ''}`} role="status">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <span>{success}</span>
          </div>

          {/* Phone step */}
          {step === 'phone' && (
            <div>
              <div className={`form-group ${phoneErrors.includes('phone') ? 'has-error' : ''} ${phoneValid ? 'has-success' : ''}`}>
                <label className="block font-bold text-sm mb-2" htmlFor="phone-input">
                  شماره موبایل
                </label>
                <div className="relative">
                  <input
                    id="phone-input"
                    type="tel"
                    className="form-input has-prefix"
                    placeholder="09123456789"
                    dir="ltr"
                    inputMode="numeric"
                    maxLength={11}
                    autoComplete="tel"
                    value={phone}
                    onChange={e => {
                      const v = e.target.value.replace(/[^0-9]/g, '')
                      setPhone(v)
                      setPhoneErrors([])
                    }}
                  />
                  <span className="phone-prefix" aria-hidden="true">۹۸+</span>
                </div>
                <div className="form-error" role="alert">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>شماره موبایل صحیح وارد کنید</span>
                </div>
              </div>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSendOtp}
                disabled={loading}
              >
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> در حال پردازش...</>
                ) : (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    ارسال کد تایید
                  </>
                )}
              </button>
            </div>
          )}

          {/* OTP step */}
          {step === 'otp' && (
            <div>
              <div className="form-group">
                <label className="block font-bold text-sm mb-2" id="otp-label">
                  کد ۶ رقمی را وارد کنید
                </label>
                <div
                  className="flex gap-2 justify-center"
                  role="group"
                  aria-labelledby="otp-label"
                  dir="ltr"
                  onPaste={handleOtpPaste}
                >
                  {otp.map((digit, idx) => (
                    <input
                      key={idx}
                      ref={el => { otpRefs.current[idx] = el }}
                      type="tel"
                      className={`otp-input ${digit ? 'filled' : ''}`}
                      maxLength={1}
                      inputMode="numeric"
                      pattern="[0-9]"
                      aria-label={`رقم ${idx + 1}`}
                      value={digit}
                      onChange={e => handleOtpChange(idx, e.target.value)}
                      onKeyDown={e => handleOtpKeyDown(idx, e)}
                      autoFocus={idx === 0}
                    />
                  ))}
                </div>
              </div>
              <div className="otp-timer text-center text-sm text-muted mb-4">
                {countdown > 0 ? (
                  <><span className="font-bold text-fg">{toPersianDigits(Math.floor(countdown / 60) < 10 ? '0' + Math.floor(countdown / 60) : Math.floor(countdown / 60))}:{toPersianDigits(countdown % 60 < 10 ? '0' + (countdown % 60) : countdown % 60)}</span> تا ارسال مجدد</>
                ) : (
                  <span className="font-bold text-fg">۰۰:۰۰</span>
                )}
              </div>
              <button
                type="button"
                className="bg-none border-none text-fg font-bold text-sm underline underline-offset-[3px] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed mx-auto block mb-5"
                onClick={handleResend}
                disabled={countdown > 0}
              >
                ارسال مجدد کد
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleVerifyOtp}
                disabled={loading || otp.join('').length !== 6}
              >
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> در حال پردازش...</>
                ) : (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                    تایید و ورود
                  </>
                )}
              </button>
              <button type="button" className="btn-ghost mt-3" onClick={backToPhone}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                تغییر شماره
              </button>
            </div>
          )}

          {/* Footer */}
          <div className="text-center mt-7 font-semibold text-sm text-muted">
            حساب کاربری ندارید؟{' '}
            <Link to="/register" className="font-extrabold text-fg underline underline-offset-[3px] hover:text-muted transition-colors">
              ثبت‌نام کنید
            </Link>
          </div>
          <div className="flex items-center gap-1.5 mt-8 font-bold text-sm text-muted">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            <Link to="/" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted">
              بازگشت به سایت
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
