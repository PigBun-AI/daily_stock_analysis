import type React from 'react';
import { UiLanguageToggle } from '../i18n/UiLanguageToggle';
import { useUiLanguage } from '../../contexts/UiLanguageContext';

type AuthShellProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export const AuthShell: React.FC<AuthShellProps> = ({ title, description, children, footer }) => {
  const { t } = useUiLanguage();

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border/20 px-6 py-4">
        <p className="text-sm font-semibold tracking-tight">{t('login.kicker')}</p>
        <UiLanguageToggle />
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-[400px] rounded-lg border border-border/20 bg-card p-7 shadow-sm">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="mt-2 text-sm leading-6 text-secondary-text">{description}</p>
          ) : null}
          <div className="mt-6">{children}</div>
        </div>
      </main>

      <footer className="border-t border-border/15 px-6 py-4 text-center text-xs text-muted-foreground">
        {footer ?? t('login.footer')}
      </footer>
    </div>
  );
};
