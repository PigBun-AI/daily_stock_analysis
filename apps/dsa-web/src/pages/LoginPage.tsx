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

const LoginPage: React.FC = () => {
  const { login, passwordSet, setupState, registrationEnabled } = useAuth();
  const { t } = useUiLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = t('login.pageTitle');
  }, [t]);
  const [searchParams] = useSearchParams();
  const redirect = resolveLoginRedirect(searchParams.get('redirect'));

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  const isFirstTime = setupState === 'no_password' || !passwordSet;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (isFirstTime && password !== passwordConfirm) {
      setError(t('login.passwordMismatch'));
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await login(
        password,
        isFirstTime ? passwordConfirm : undefined,
        isFirstTime ? undefined : username.trim() || undefined,
      );
      if (result.success) {
        navigate(redirect, { replace: true });
      } else {
        setError(result.error ?? t('login.loginFailed'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthShell
      title={isFirstTime ? t('login.setupTitle') : t('login.adminLogin')}
      description={isFirstTime ? t('login.setupDescription') : t('login.loginDescription')}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {!isFirstTime && (
          <Input
            id="username"
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
        )}

        <Input
          id="password"
          type="password"
          appearance="login"
          allowTogglePassword
          label={isFirstTime ? t('login.adminPassword') : t('login.loginPassword')}
          placeholder={t('login.loginPasswordPlaceholder')}
          hint={t('login.passwordHint')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isSubmitting}
          autoFocus={isFirstTime}
          autoComplete={isFirstTime ? 'new-password' : 'current-password'}
        />

        {isFirstTime && (
          <Input
            id="passwordConfirm"
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
        )}

        {error && (
          <SettingsAlert
            title={isFirstTime ? t('login.setupFailed') : t('login.validationFailed')}
            message={isParsedApiError(error) ? error.message : error}
            variant="error"
          />
        )}

        <Button type="submit" variant="primary" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{isFirstTime ? t('login.setupSubmitting') : t('login.loginSubmitting')}</span>
            </>
          ) : (
            <span>{isFirstTime ? t('login.setupSubmit') : t('login.loginSubmit')}</span>
          )}
        </Button>
      </form>

      {!isFirstTime && registrationEnabled !== false && (
        <p className="mt-6 text-sm text-secondary-text">
          {t('login.noAccount')}{' '}
          <Link
            to={`/register?redirect=${encodeURIComponent(redirect)}`}
            className="text-primary underline underline-offset-4 hover:opacity-80"
          >
            {t('login.goRegister')}
          </Link>
        </p>
      )}
    </AuthShell>
  );
};

export default LoginPage;
