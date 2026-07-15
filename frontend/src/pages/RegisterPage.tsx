import { useState } from 'react'
import { Link } from 'react-router-dom'

const PERSIAN_DIGITS = ['?', '?', '?', '?', '?', '?', '?', '?', '?', '?']
function toPersianDigits(s: string | number) {
  return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d])
}

const PHONE_REGEX = /^09[0-9]{9}$/

export default function RegisterPage() {
  const [step, setStep] = useState<'phone' | 'otp'>('phone')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [phoneErrors, setPhoneErrors] = useState<string[]>([])
  const [termsAccepted, setTermsAccepted] = useState(false)

  const phoneValid = PHONE_REGEX.test(phone)

  const clearAlerts = () => { setError(''); setSuccess('') }

  const handleSendOtp = async () => {
    clearAlerts()
    const errs: string[] = []
    if (!phone) errs.push('phone')
    else if (!PHONE_REGEX.test(phone)) errs.push('phone')
    setPhoneErrors(errs)
    if (errs.length) return

    if (!termsAccepted) {
      setError('????? ?????? ? ????? ?? ???????')
      return
    }

    setLoading(true)
    await new Promise(r => setTimeout(r, 1500))
    setLoading(false)

    setStep('otp')
    setCountdown(120)
    setSuccess('?? ????? ?? ????? ' + toPersianDigits(phone.slice(0, 4)) + '****' + toPersianDigits(phone.slice(-2)) + ' ????? ??')
  }

  const handleOtpChange = (idx: number, value: string) => {
    const digit = value.replace(/[^0-9]/g, '').slice(-1)
    setOtp(prev => { const n = [...prev]; n[idx] = digit; return n })
    if (digit && idx < 5) {
      document.querySelector<HTMLInputElement>('#reg-otp-' + (idx + 1))?.focus()
    }
  }

  const handleOtpKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      setOtp(prev => { const n = [...prev]; n[idx - 1] = ''; return n })
      document.querySelector<HTMLInputElement>('#reg-otp-' + (idx - 1))?.focus()
    }
  }

  const handleVerifyOtp = async () => {
    clearAlerts()
    if (otp.join('').length !== 6) return
    setLoading(true)
    await new Promise(r => setTimeout(r, 1500))
    setLoading(false)
    setSuccess('??????? ?? ?????? ????? ??!')
  }

  const backToPhone = () => {
    setStep('phone')
    setOtp(['', '', '', '', '', ''])
    clearAlerts()
    setCountdown(0)
    setPhoneErrors([])
  }

  return (
    <div className="flex flex-col min-h-screen lg:flex-row">
      <aside className="hidden lg:flex lg:w-[46%] bg-surface border-l-[3px] border-border items-center justify-center relative overflow-hidden" aria-hidden="true">
        <div className="relative w-full h-full flex items-center justify-center p-12">
          <div className="w-full max-w-[520px] aspect-[4/3] bg-gradient-to-br from-[#A8DFF0] via-[#B8F0D8] to-[#D4C5F9] border-[3px] border-border shadow-[6px_6px_0_#1A1A1A] flex flex-col items-center justify-center p-10 text-center" role="img" aria-label="?????? ?????? ??????">
            <span className="text-5xl mb-4">??</span>
            <span className="text-lg font-bold text-muted">?? ??????? ?????? ?????? ????????</span>
          </div>
          <div className="absolute bottom-8 right-8 w-[50px] h-[50px] border-b-[3px] border-r-[3px] border-border" aria-hidden="true" />
          <div className="absolute top-8 left-8 w-[50px] h-[50px] border-t-[3px] border-l-[3px] border-border" aria-hidden="true" />
        </div>
      </aside>

      <main className="flex-1 flex flex-col items-center justify-center px-5 py-10 lg:py-16 lg:px-16" role="main">
        <div className="w-full max-w-[420px]">
          <div className="lg:hidden flex items-center justify-center gap-2 mb-2" aria-hidden="true">
            <span className="w-[10px] h-[10px] bg-accent-neon border-2 border-border" />
            <span className="text-2xl font-black tracking-tight">?????? ??????</span>
          </div>
          <p className="lg:hidden text-center text-muted font-semibold text-sm mb-8">?????? ?????? ??????</p>

          <h1 className="text-2xl font-black mb-1">???????</h1>
          <p className="text-muted font-medium text-sm mb-7">????? ?????? ??? ?? ???? ????</p>

          <div className={'alert ' + (error ? 'alert-error visible' : '')} role="alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{error}</span>
          </div>
          <div className={'alert ' + (success ? 'alert-success visible' : '')} role="status">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <span>{success}</span>
          </div>

          {step === 'phone' && (
            <div>
              <div className={'form-group ' + (phoneErrors.includes('phone') ? 'has-error' : '') + ' ' + (phoneValid ? 'has-success' : '')}>
                <label className="block font-bold text-sm mb-2" htmlFor="reg-phone-input">????? ??????</label>
                <div className="relative">
                  <input id="reg-phone-input" type="tel" className="form-input has-prefix" placeholder="09123456789" dir="ltr" inputMode="numeric" maxLength={11} autoComplete="tel" value={phone}
                    onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ''); setPhone(v); setPhoneErrors([]) }} />
                  <span className="phone-prefix" aria-hidden="true">??+</span>
                </div>
                <div className="form-error" role="alert">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>????? ?????? ???? ???? ????</span>
                </div>
              </div>

              <div className="flex items-start gap-2 mt-4 mb-6">
                <input id="reg-terms" type="checkbox" className="mt-0.5 w-5 h-5 border-3 border-border bg-surface appearance-none checked:bg-accent-neon checked:border-border shrink-0 cursor-pointer"
                  checked={termsAccepted} onChange={e => setTermsAccepted(e.target.checked)} />
                <label htmlFor="reg-terms" className="text-sm font-semibold text-muted cursor-pointer leading-relaxed">
                  <a href="/terms" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted transition-colors">?????? ? ?????</a> ?? ?????? ? ????????
                </label>
              </div>

              <button type="button" className="btn-primary" onClick={handleSendOtp} disabled={loading}>
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> ?? ??? ??????...</>
                ) : (
                  <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> ???????</>
                )}
              </button>

              <p className="text-center mt-6 text-sm font-semibold text-muted">
                <span>????? ??????? ????????? </span>
                <Link to="/login" className="font-extrabold text-fg underline underline-offset-[3px] hover:text-muted transition-colors">???? ????</Link>
              </p>
            </div>
          )}

          {step === 'otp' && (
            <div>
              <div className="form-group">
                <label className="block font-bold text-sm mb-2" id="reg-otp-label">?? ? ???? ?? ???? ????</label>
                <div className="flex gap-2 justify-center" role="group" aria-labelledby="reg-otp-label" dir="ltr">
                  {otp.map((digit, idx) => (
                    <input key={idx} id={'reg-otp-' + idx} type="tel" className={'otp-input ' + (digit ? 'filled' : '')} maxLength={1} inputMode="numeric" pattern="[0-9]" aria-label={'??? ' + (idx + 1)}
                      value={digit} onChange={e => handleOtpChange(idx, e.target.value)} onKeyDown={e => handleOtpKeyDown(idx, e)} autoFocus={idx === 0} />
                  ))}
                </div>
              </div>
              <div className="text-center text-sm text-muted mb-4">
                {countdown > 0 ? (
                  <><span className="font-bold text-fg">{toPersianDigits(Math.floor(countdown / 60) < 10 ? '0' + Math.floor(countdown / 60) : Math.floor(countdown / 60))}:{toPersianDigits(countdown % 60 < 10 ? '0' + (countdown % 60) : countdown % 60)}</span> ?? ????? ????</>
                ) : (
                  <span className="font-bold text-fg">??:??</span>
                )}
              </div>
              <button type="button" className="bg-none border-none text-fg font-bold text-sm underline underline-offset-[3px] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed mx-auto block mb-5"
                onClick={() => { setCountdown(120); setSuccess('?? ????? ?????? ????? ??') }} disabled={countdown > 0}>
                ????? ???? ??
              </button>
              <button type="button" className="btn-primary" onClick={handleVerifyOtp} disabled={loading || otp.join('').length !== 6}>
                {loading ? (
                  <><span className="spinner" aria-hidden="true" /> ?? ??? ??????...</>
                ) : (
                  <><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg> ????? ? ???????</>
                )}
              </button>
              <button type="button" className="btn-ghost mt-3" onClick={backToPhone}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                ????? ?????
              </button>
            </div>
          )}

          <div className="flex items-center gap-1.5 mt-8 font-bold text-sm text-muted">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            <Link to="/" className="text-fg font-extrabold underline underline-offset-[2px] hover:text-muted">?????? ?? ????</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
