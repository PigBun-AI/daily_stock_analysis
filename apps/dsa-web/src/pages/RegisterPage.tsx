import type React from 'react';
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Input } from '../components/common';
import { UiLanguageToggle } from '../components/i18n/UiLanguageToggle';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { useAuth } from '../hooks';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { SettingsAlert } from '../components/settings';
import { resolveLoginRedirect } from '../utils/loginRedirect';

const RegisterPage: React.FC = () => {
  const { register, registrationEnabled } = useAuth();
  const { t } = useUiLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirect = resolveLoginRedirect(searchParams.get('redirect'));

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  useEffect(() => {
    document.title = t('register.pageTitle');
  }, [t]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== passwordConfirm) {
      setError(t('login.passwordMismatch'));
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await register(username.trim(), password, passwordConfirm);
      if (result.success) {
        navigate(redirect, { replace: true });
      } else {
        setError(result.error ?? t('register.failed'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-[var(--login-bg-main)] text-[var(--login-text-primary)]">
      <header className="flex items-center justify-between border-b border-[var(--login-border-card)] px-6 py-4 sm:px-10">
        <p className="text-[11px] font-medium uppercase tracking-[0.28em] text-[var(--login-text-muted)]">
          {t('login.kicker')}
        </p>
        <UiLanguageToggle />
      </header>

      <main className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 px-6 py-16 sm:px-10 lg:grid-cols-12 lg:gap-16 lg:py-24">
        <section className="lg:col-span-6">
          <p className="text-[11px] font-medium uppercase tracking-[0.32em] text-[var(--login-accent-text)]">
            02 / {t('register.sectionIndex')}
          </p>
          <h1 className="mt-6 max-w-xl text-5xl font-semibold leading-[0.95] tracking-tight sm:text-7xl">
            {t('register.brandTitle')}
          </h1>
          <p className="mt-8 max-w-md text-sm leading-relaxed text-[var(--login-text-secondary)]">
            {t('register.description')}
          </p>
        </section>

        <section className="mt-12 border-t border-[var(--login-border-card)] pt-10 lg:col-span-6 lg:mt-0 lg:border-l lg:border-t-0 lg:pl-16 lg:pt-0">
          <h2 className="text-2xl font-semibold tracking-tight">{t('register.title')}</h2>
          {registrationEnabled === false ? (
            <p className="mt-6 text-sm text-[var(--login-text-secondary)]">{t('register.disabled')}</p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-10 space-y-6">
              <Input
                id="register-username"
                type="text"
                appearance="login"
                label={t('login.username')}
                placeholder={t('login.usernamePlaceholder')}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isSubmitting}
                autoFocus
                autoComplete="username"
              />
              <Input
                id="register-password"
                type="password"
                appearance="login"
                allowTogglePassword
                iconType="password"
                label={t('login.loginPassword')}
                placeholder={t('login.setupPasswordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
              />
              <Input
                id="register-password-confirm"
                type="password"
                appearance="login"
                allowTogglePassword
                iconType="password"
                label={t('login.confirmPassword')}
                placeholder={t('login.confirmPasswordPlaceholder')}
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
              />

              {error && (
                <SettingsAlert
                  title={t('register.failed')}
                  message={isParsedApiError(error) ? error.message : error}
                  variant="error"
                  className="!border-[var(--login-error-border)] !bg-[var(--login-error-bg)] !text-[var(--login-error-text)]"
                />
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="h-12 w-full rounded-none border-0 bg-[var(--login-brand-button-start)] font-medium tracking-wide text-[var(--login-button-text)]"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>{t('register.submitting')}</span>
                  </>
                ) : (
                  <span>{t('register.submit')}</span>
                )}
              </Button>
            </form>
          )}

          <p className="mt-8 border-t border-[var(--login-border-card)] pt-6 text-sm text-[var(--login-text-secondary)]">
            {t('register.hasAccount')}{' '}
            <Link
              to={`/login?redirect=${encodeURIComponent(redirect)}`}
              className="font-medium text-[var(--login-accent-text)] underline-offset-4 hover:underline"
            >
              {t('register.goLogin')}
            </Link>
          </p>
        </section>
      </main>
    </div>
  );
};

export default RegisterPage;
