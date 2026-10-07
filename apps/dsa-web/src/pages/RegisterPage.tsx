import type React from 'react';
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Input } from '../components/common';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { useAuth } from '../hooks';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { AuthShell } from '../components/layout/AuthShell';
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
    <AuthShell title={t('register.title')} description={t('register.description')}>
      {registrationEnabled === false ? (
        <p className="text-sm text-secondary-text">{t('register.disabled')}</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
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
            label={t('login.loginPassword')}
            placeholder={t('login.loginPasswordPlaceholder')}
            hint={t('login.passwordHint')}
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
            />
          )}

          <Button type="submit" variant="primary" size="lg" className="h-11 w-full" disabled={isSubmitting}>
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

      <p className="mt-6 text-sm text-secondary-text">
        {t('register.hasAccount')}{' '}
        <Link
          to={`/login?redirect=${encodeURIComponent(redirect)}`}
          className="text-primary underline underline-offset-4 hover:opacity-80"
        >
          {t('register.goLogin')}
        </Link>
      </p>
    </AuthShell>
  );
};

export default RegisterPage;
