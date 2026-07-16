import { useState, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerSms, verifySms, requestSms, getErrorMessage } from '../lib/api'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) {
  return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d])
}

const PHONE_REGEX = /^09[0-9]{9}$/
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function RegisterPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'profile' | 'otp'>('profile')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [errors, setErrors] = useState<Record<string, boolean>>({})
  const [termsAccepted, setTermsAccepted] = useState(false)
  const otpRefs = useRef<(HTMLInputElement | null)[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined)

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
    const errs: Record<string, boolean> = {}
    if (!firstName.trim()) errs.firstName = true
    if (!lastName.trim()) errs.lastName = true
    if (!EMAIL_REGEX.test(email)) errs.email = true
    if (!PHONE_REGEX.test(phone)) errs.phone = true
    setErrors(errs)
    if (Object.keys(errs).length) return

    if (!termsAccepted) {
      setError('لطفاً شرایط و قوانین را بپذیرید')
      return
    }

    setLoading(true)
    try {
      await registerSms({
        phone,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim() || null,
      })
      setStep('otp')
      startCountdown()
      setSuccess('کد تایید به شماره ' + toPersianDigits(phone.slice(0, 4)) + '****' + toPersianDigits(phone.slice(-2)) + ' ارسال شد')
      setTimeout(() => otpRefs.current[0]?.focus(), 100)
    } catch (e) {
      setError(getErrorMessage(e, 'خطا در ارسال کد تایید'))
    } finally {
      setLoading(false)
    }
  }

  const handleOtpChange = (idx: number, value: string) => {
    const digit = value.replace(/[^0-9]/g, '').slice(-1)
    setOtp(prev => {
      const n = [...prev]
      n[idx] = digit
      return n
    })
    if (digit && idx < 5) {
      otpRefs.current[idx + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      setOtp(prev => {
        const n = [...prev]
        n[idx - 1] = ''
        return n
      })
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
    try {
      const res = await verifySms({ phone, code })
      if (res.user) localStorage.setItem('user', JSON.stringify(res.user))
      setSuccess('ثبت‌نام با موفقیت انجام شد! در حال انتقال...')
      setTimeout(() => navigate('/'), 1200)
    } catch (e) {
      setError(getErrorMessage(e, 'کد وارد شده صحیح نیست'))
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    clearAlerts()
    setLoading(true)
    try {
      await requestSms({ phone })
      setSuccess('کد تایید مجدداً ارسال شد')
      startCountdown()
      setOtp(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } catch (e) {
      setError(getErrorMessage(e, 'خطا در ارسال مجدد کد'))
    } finally {
      setLoading(false)
    }
  }

  const backToProfile = () => {
    setStep('profile')
    setOtp(['', '', '', '', '', ''])
    clearAlerts()
    clearInterval(timerRef.current)
    setCountdown(0)
  }

  const clearFieldError = (field: string) => {
    setErrors(prev => { const n = { ...prev }; delete n[field]; return n })
  }

  const fieldClass = (field: string, isValid: boolean) =>
    'form-group ' + (errors[field] ? 'has-error' : '') + ' ' + (isValid ? 'has-success' : '')

  return (
    <div className="flex flex-col min-h-screen lg:flex-row">
      {/* Desktop brand panel */}
      <aside className="hidden lg:flex lg:w-[46%] bg-surface border-s-[3px] border-border items-center justify-center relative overflow-hidden" aria-hidden="true">
        <div className="relative w-full h-full flex items-center justify-center p-12">
          <img
            src="/brand-login.png"
            alt="پلتفرم دیدار — داشبورد دیدپذیری هوش مصنوعی"
            className="w-full max-w-[520px] max-h-[70vh] object-contain border-[3px] border-border shadow-[6px_6px_0_#1A1A1A] block"
          />
          <div className="absolute bottom-8 start-8 w-[50px] h-[50px] border-b-[3px] border-s-[3px] border-border" aria-hidden="true" />
          <div className="absolute top-8 end-8 w-[50px] h-[50px] border-t-[3px] border-e-[3px] border-border" aria-hidden="true" />
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex flex-col items-center justify-center px-5 py-10 lg:py-16 lg:px-16" role="main">
        <div className="w-full max-w-[420px]">
          {/* Mobile brand */}
          <div className="lg:hidden flex items-center justify-center gap-2.5 mb-2" aria-hidden="true">
            <span className="w-[10px] h-[10px] bg-accent-neon border-2 border-border" />
            <span className="text-2xl font-black tracking-tight">دیدار</span>
          </div>
          <p className="lg:hidden text-center text-muted font-semibold text-sm mb-8">
            دیدپذیری هوش مصنوعی برای برند شما
          </p>

          <h1 className="text-[1.6rem] font-black mb-1.5">ایجاد حساب کاربری</h1>
          <p className="text-muted font-medium text-sm mb-7">
            اطلاعات خود را وارد کنید و با کد تایید ثبت‌نام کنید
          </p>

          {/* Alerts */}
          <div className={'alert ' + (error ? 'alert-error visible' : '')} role="alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{error}</span>
          </div>
          <div className={'alert ' + (success ? 'alert-success visible' : '')} role="status">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <span>{success}</span>
          </div>

          {/* Profile step */}
          {step === 'profile' && (
            <div>
              <div className="flex gap-3">
                <div className={fieldClass('firstName', firstName.trim().length > 0) + ' flex-1'}>
                  <label className="block font-bold text-sm mb-2" htmlFor="fname-input">نام</label>
                  <input id="fname-input" type="text" className="form-input" placeholder="علی" autoComplete="given-name" value={firstName}
                    onChange={e => { setFirstName(e.target.value); clearFieldError('firstName') }} />
                  <div className="form-error" role="alert">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <span>نام را وارد کنید</span>
                  </div>
                </div>
                <div className={fieldClass('lastName', lastName.trim().length > 0) + ' flex-1'}>
                  <label className="block font-bold text-sm mb-2" htmlFor="lname-input">نام خانوادگی</label>
                  <input id="lname-input" type="text" className="form-input" placeholder="رضایی" autoComplete="family-name" value={lastName}
                    onChange={e => { setLastName(e.target.value); clearFieldError('lastName') }} />
                  <div className="form-error" role="alert">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <span>نام خانوادگی را وارد کنید</span>
                  </div>
                </div>
              </div>

              <div className={fieldClass('email', EMAIL_REGEX.test(email))}>
                <label className="block font-bold text-sm mb-2" htmlFor="email-input">آدرس ایمیل</label>
                <input id="email-input" type="email" className="form-input" placeholder="ali@example.com" dir="ltr" autoComplete="email" value={email}
                  onChange={e => { setEmail(e.target.value); clearFieldError('email') }} />
                <div className="form-error" role="alert">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>ایمیل صحیح وارد کنید</span>
                </div>
              </div>

              <div className={fieldClass('phone', PHONE_REGEX.test(phone))}>
                <label className="block font-bold text-sm mb-2" htmlFor="phone-input">شماره موبایل</label>
                <div className="relative">
                  <input id="phone-input" type="tel" className="form-input has-prefix" placeholder="09123456789" dir="ltr" inputMode="numeric" maxLength={11} autoComplete="tel" value={phone}
                    onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ''); setPhone(v); clearFieldError('phone') }} />
                  <span className="phone-prefix" aria-hidden="true">۹۸+</span>
                </div>
                <div className="form-error" role="alert">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>شماره موبایل صحیح وارد کنید (مثال: ۰۹۱۲۱۲۳۴۵۶۷)</span>
                </div>
              </div>

              <div className="flex items-start gap-2.5 mb-6 text-sm font-semibold text-muted leading-relaxed">
                <input id="terms" type="checkbox" className="mt-0.5 w-5 h-5 accent-accent-neon border-3 border-border shrink-0 cursor-pointer"
                  checked={termsAccepted} onChange={e => setTermsAccepted(e.target.checked)} />
                <label htmlFor="terms" className="cursor-pointer">
                  <a href="/terms" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted transition-colors">شرایط و قوانین</a>
                  {' '}و{' '}
                  <a href="/privacy" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted transition-colors">حریم خصوصی</a>
                  {' '}را مطالعه کرده و می‌پذیرم
                </label>
              </div>

              <button type="button" className="btn-primary" onClick={handleSendOtp} disabled={loading}>
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> در حال پردازش...</>
                ) : (
                  <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> ارسال کد تایید</>
                )}
              </button>
            </div>
          )}

          {/* OTP step */}
          {step === 'otp' && (
            <div>
              <div className="form-group">
                <label className="block font-bold text-sm mb-2" id="otp-label">کد ۶ رقمی را وارد کنید</label>
                <div className="flex gap-2 justify-center" role="group" aria-labelledby="otp-label" dir="ltr" onPaste={handleOtpPaste}>
                  {otp.map((digit, idx) => (
                    <input
                      key={idx}
                      ref={el => { otpRefs.current[idx] = el }}
                      type="tel"
                      className={'otp-input ' + (digit ? 'filled' : '')}
                      maxLength={1}
                      inputMode="numeric"
                      pattern="[0-9]"
                      aria-label={'رقم ' + (idx + 1)}
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
              <button type="button" className="bg-none border-none text-fg font-bold text-sm underline underline-offset-[3px] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed mx-auto block mb-5"
                onClick={handleResend} disabled={countdown > 0}>
                ارسال مجدد کد
              </button>
              <button type="button" className="btn-primary" onClick={handleVerifyOtp} disabled={loading || otp.join('').length !== 6}>
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> در حال پردازش...</>
                ) : (
                  <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg> تایید و تکمیل ثبت‌نام</>
                )}
              </button>
              <button type="button" className="btn-ghost mt-3" onClick={backToProfile}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                تغییر اطلاعات
              </button>
            </div>
          )}

          {/* Footer */}
          <div className="text-center mt-7 font-semibold text-sm text-muted">
            قبلاً ثبت‌نام کرده‌اید؟{' '}
            <Link to="/login" className="font-extrabold text-fg underline underline-offset-[3px] hover:text-muted transition-colors">ورود کنید</Link>
          </div>
          <div className="flex items-center gap-1.5 mt-8 font-bold text-sm text-muted">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            <Link to="/" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted">بازگشت به سایت</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
