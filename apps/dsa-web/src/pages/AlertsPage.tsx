import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { BellRing } from 'lucide-react';
import { alertsApi } from '../api/alerts';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { AlertRuleForm } from '../components/alerts/AlertRuleForm';
import {
  AlertRuleList,
  type AlertRuleBusyState,
  type AlertRuleEnabledFilter,
  type AlertTypeFilter,
} from '../components/alerts/AlertRuleList';
import { AlertTriggerHistory } from '../components/alerts/AlertTriggerHistory';
import { ApiErrorAlert, AppPage, Card, EmptyState, InlineAlert, Loading, PageHeader } from '../components/common';
import type {
  AlertNotificationItem,
  AlertRuleCreateRequest,
  AlertRuleItem,
  AlertRuleListResponse,
  AlertRuleTestResponse,
  AlertTriggerItem,
  AlertType,
} from '../types/alerts';
import { formatDateTime } from '../utils/format';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiTextKey, UiTextParams } from '../i18n/uiText';

type Translate = (key: UiTextKey, params?: UiTextParams) => string;

const PAGE_SIZE = 20;

function enabledFilterToQuery(value: AlertRuleEnabledFilter): boolean | undefined {
  if (value === 'enabled') return true;
  if (value === 'disabled') return false;
  return undefined;
}

function alertTypeFilterToQuery(value: AlertTypeFilter): AlertType | undefined {
  return value === 'all' ? undefined : value;
}

function testVariant(result: AlertRuleTestResponse): 'success' | 'warning' | 'danger' {
  if (result.status === 'evaluation_error') return 'danger';
  return result.triggered ? 'success' : 'warning';
}

function renderTestResultMessage(result: AlertRuleTestResponse, t: Translate): React.ReactNode {
  const targetResults = result.targetResults ?? [];
  return (
    <div className="space-y-2">
      <div>
        {result.message}
        {` · ${t('alerts.testStatus')}：`}
        {result.status}
        {` · ${t('alerts.testTriggered')}：`}
        {result.triggered ? t('alerts.testYes') : t('alerts.testNo')}
        {` · ${t('alerts.testObserved')}：`}
        {result.observedValue == null ? '--' : String(result.observedValue)}
      </div>
      {result.evaluatedCount != null && result.evaluatedCount > 1 ? (
        <div className="text-xs">
          {t('alerts.testSummary', {
            evaluated: result.evaluatedCount,
            triggered: result.triggeredCount ?? 0,
            degraded: result.degradedCount ?? 0,
            skipped: result.skippedCount ?? 0,
          })}
        </div>
      ) : null}
      {targetResults.length > 1 ? (
        <div className="grid gap-1 text-xs">
          {targetResults.slice(0, 20).map((item) => (
            <div key={`${item.target}-${item.status}`} className="flex flex-wrap justify-between gap-2">
              <span>{item.displayTarget ?? item.target}</span>
              <span>
                {item.status}
                {item.recordStatus ? ` / ${item.recordStatus}` : ''}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function formatNotificationChannel(channel: string, t: Translate): string {
  const labels: Record<string, string> = {
    __cooldown__: t('alerts.channel.cooldown'),
    __cooldown_read_failed__: t('alerts.channel.cooldownReadFailed'),
    __noise_suppressed__: t('alerts.channel.noiseSuppressed'),
    __no_channel__: t('alerts.channel.noChannel'),
    __dispatch__: t('alerts.channel.dispatch'),
    __context__: t('alerts.channel.context'),
  };
  return labels[channel] ?? channel;
}

function formatNotificationStatus(notification: AlertNotificationItem, t: Translate): string {
  if (notification.success) return t('alerts.status.success');
  if (notification.errorCode === 'cooldown_active') return t('alerts.status.cooldownActive');
  if (notification.errorCode === 'cooldown_read_failed') return t('alerts.status.cooldownReadFailed');
  if (notification.errorCode === 'noise_suppressed') return t('alerts.status.noiseSuppressed');
  if (notification.errorCode === 'no_channel') return t('alerts.status.noChannel');
  return t('alerts.status.failed');
}

const AlertsPage: React.FC = () => {
  const { t } = useUiLanguage();

  useEffect(() => {
    document.title = t('alerts.pageTitle');
  }, [t]);

  const [rules, setRules] = useState<AlertRuleItem[]>([]);
  const [rulesTotal, setRulesTotal] = useState(0);
  const [ruleSources, setRuleSources] = useState<AlertRuleListResponse['ruleSources']>(null);
  const [rulesPage, setRulesPage] = useState(1);
  const [enabledFilter, setEnabledFilter] = useState<AlertRuleEnabledFilter>('all');
  const [alertTypeFilter, setAlertTypeFilter] = useState<AlertTypeFilter>('all');
  const [rulesLoading, setRulesLoading] = useState(false);
  const [rulesError, setRulesError] = useState<ParsedApiError | null>(null);
  const [rulesLoaded, setRulesLoaded] = useState(false);
  const [rulesRefreshKey, setRulesRefreshKey] = useState(0);

  const [triggers, setTriggers] = useState<AlertTriggerItem[]>([]);
  const [triggersLoading, setTriggersLoading] = useState(false);
  const [triggersError, setTriggersError] = useState<ParsedApiError | null>(null);

  const [notifications, setNotifications] = useState<AlertNotificationItem[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState<ParsedApiError | null>(null);

  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<ParsedApiError | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [busyRule, setBusyRule] = useState<AlertRuleBusyState | null>(null);
  const [testResult, setTestResult] = useState<AlertRuleTestResponse | null>(null);
  const rulesRequestIdRef = useRef(0);

  const loadRules = useCallback(async () => {
    const requestId = rulesRequestIdRef.current + 1;
    rulesRequestIdRef.current = requestId;
    const isLatestRequest = () => rulesRequestIdRef.current === requestId;
    const requestedPage = rulesPage;
    const baseQuery = {
      enabled: enabledFilterToQuery(enabledFilter),
      alertType: alertTypeFilterToQuery(alertTypeFilter),
      pageSize: PAGE_SIZE,
    };
    setRulesLoading(true);
    try {
      let response = await alertsApi.listRules({ ...baseQuery, page: requestedPage });
      if (!isLatestRequest()) return null;
      const lastPage = Math.max(1, Math.ceil(response.total / PAGE_SIZE));
      if (response.items.length === 0 && response.total > 0 && requestedPage > lastPage) {
        setRulesPage(lastPage);
        response = await alertsApi.listRules({ ...baseQuery, page: lastPage });
        if (!isLatestRequest()) return null;
      }
      setRules(response.items);
      setRulesTotal(response.total);
      setRuleSources(response.ruleSources ?? null);
      setRulesError(null);
      setRulesLoaded(true);
      return response;
    } catch (error) {
      if (!isLatestRequest()) return null;
      setRulesError(getParsedApiError(error));
      return null;
    } finally {
      if (isLatestRequest()) {
        setRulesLoading(false);
      }
    }
  }, [alertTypeFilter, enabledFilter, rulesPage]);

  const loadTriggers = useCallback(async () => {
    setTriggersLoading(true);
    try {
      const response = await alertsApi.listTriggers({ page: 1, pageSize: PAGE_SIZE });
      setTriggers(response.items);
      setTriggersError(null);
    } catch (error) {
      setTriggersError(getParsedApiError(error));
    } finally {
      setTriggersLoading(false);
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    setNotificationsLoading(true);
    try {
      const response = await alertsApi.listNotifications({ page: 1, pageSize: PAGE_SIZE });
      setNotifications(response.items);
      setNotificationsError(null);
    } catch (error) {
      setNotificationsError(getParsedApiError(error));
    } finally {
      setNotificationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRules();
  }, [loadRules, rulesRefreshKey]);

  useEffect(() => {
    if (!rulesLoaded) return;
    void loadTriggers();
    void loadNotifications();
  }, [loadNotifications, loadTriggers, rulesLoaded]);

  const handleCreateRule = async (payload: AlertRuleCreateRequest) => {
    setCreateLoading(true);
    setCreateError(null);
    setCreateSuccess(null);
    try {
      const created = await alertsApi.createRule(payload);
      setCreateSuccess(t('alerts.createSuccessWithName', { name: created.name }));
      setRulesPage(1);
      setRulesRefreshKey((value) => value + 1);
      return true;
    } catch (error) {
      setCreateError(getParsedApiError(error));
      return false;
    } finally {
      setCreateLoading(false);
    }
  };

  const handleToggleEnabled = async (rule: AlertRuleItem) => {
    setBusyRule({ id: rule.id, action: 'toggle' });
    try {
      if (rule.enabled) {
        await alertsApi.disableRule(rule.id);
      } else {
        await alertsApi.enableRule(rule.id);
      }
      setRulesRefreshKey((value) => value + 1);
    } catch (error) {
      setRulesError(getParsedApiError(error));
    } finally {
      setBusyRule(null);
    }
  };

  const handleDeleteRule = async (rule: AlertRuleItem) => {
    setBusyRule({ id: rule.id, action: 'delete' });
    try {
      await alertsApi.deleteRule(rule.id);
      setRulesRefreshKey((value) => value + 1);
    } catch (error) {
      setRulesError(getParsedApiError(error));
    } finally {
      setBusyRule(null);
    }
  };

  const handleTestRule = async (rule: AlertRuleItem) => {
    setBusyRule({ id: rule.id, action: 'test' });
    setTestResult(null);
    try {
      const result = await alertsApi.testRule(rule.id);
      setTestResult(result);
    } catch (error) {
      setRulesError(getParsedApiError(error));
    } finally {
      setBusyRule(null);
    }
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow={t('alerts.eyebrow')}
        title={t('alerts.title')}
        description={t('alerts.description')}
      />

      {createError ? <ApiErrorAlert error={createError} onDismiss={() => setCreateError(null)} /> : null}
      {createSuccess ? (
        <InlineAlert
          title={t('alerts.createSuccess')}
          message={createSuccess}
          variant="success"
          action={(
            <button type="button" className="text-sm underline" onClick={() => setCreateSuccess(null)}>
              {t('alerts.close')}
            </button>
          )}
        />
      ) : null}
      {rulesError ? <ApiErrorAlert error={rulesError} onDismiss={() => setRulesError(null)} /> : null}
      {!rulesError && ruleSources && ruleSources.legacyConfigured > 0 ? (
        <InlineAlert
          title={t('alerts.legacyTitle')}
          variant="warning"
          message={t('alerts.legacyMessage', {
            configured: ruleSources.legacyConfigured,
            effective: ruleSources.legacyEffective,
          })}
        />
      ) : null}

      <div className="grid items-stretch gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <AlertRuleForm onSubmit={handleCreateRule} isSubmitting={createLoading} />
        <div className="flex h-full min-h-0 flex-col gap-4">
          <AlertRuleList
            className="flex h-full min-h-0 flex-col"
            rules={rules}
            total={rulesTotal}
            page={rulesPage}
            pageSize={PAGE_SIZE}
            isLoading={rulesLoading}
            enabledFilter={enabledFilter}
            alertTypeFilter={alertTypeFilter}
            onEnabledFilterChange={(value) => {
              setEnabledFilter(value);
              setRulesPage(1);
            }}
            onAlertTypeFilterChange={(value) => {
              setAlertTypeFilter(value);
              setRulesPage(1);
            }}
            onPageChange={setRulesPage}
            onToggleEnabled={(rule) => void handleToggleEnabled(rule)}
            onDelete={(rule) => void handleDeleteRule(rule)}
            onTest={(rule) => void handleTestRule(rule)}
            busyRule={busyRule}
          />
          {testResult ? (
            <InlineAlert
              title={t('alerts.testResult')}
              variant={testVariant(testResult)}
              message={renderTestResultMessage(testResult, t)}
            />
          ) : null}
        </div>
      </div>

      {triggersError ? <ApiErrorAlert error={triggersError} onDismiss={() => setTriggersError(null)} /> : null}
      <AlertTriggerHistory triggers={triggers} isLoading={triggersLoading} />

      {notificationsError ? <ApiErrorAlert error={notificationsError} onDismiss={() => setNotificationsError(null)} /> : null}
      <Card title={t('alerts.notificationsTitle')} subtitle={t('alerts.notificationsSubtitle')} variant="bordered" padding="md">
        {notificationsLoading ? <Loading label={t('alerts.notificationsLoading')} /> : null}
        {!notificationsLoading && notifications.length === 0 ? (
          <EmptyState
            icon={<BellRing className="h-6 w-6" />}
            title={t('alerts.notificationsEmptyTitle')}
            description={t('alerts.notificationsEmptyDescription')}
          />
        ) : null}
        {!notificationsLoading && notifications.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="border-b border-border/60 text-xs font-medium text-muted-text">
                <tr>
                  <th className="px-3 py-2 font-medium">{t('alerts.colChannel')}</th>
                  <th className="px-3 py-2 font-medium">{t('alerts.colStatus')}</th>
                  <th className="px-3 py-2 font-medium">{t('alerts.colError')}</th>
                  <th className="px-3 py-2 font-medium">{t('alerts.colLatency')}</th>
                  <th className="px-3 py-2 font-medium">{t('alerts.colTime')}</th>
                  <th className="px-3 py-2 font-medium">{t('alerts.colDiagnostics')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {notifications.map((notification) => (
                  <tr key={notification.id}>
                    <td className="px-3 py-3">{formatNotificationChannel(notification.channel, t)}</td>
                    <td className="px-3 py-3">{formatNotificationStatus(notification, t)}</td>
                    <td className="px-3 py-3">{notification.errorCode ?? '--'}</td>
                    <td className="px-3 py-3">{notification.latencyMs == null ? '--' : `${notification.latencyMs}ms`}</td>
                    <td className="px-3 py-3">{formatDateTime(notification.createdAt)}</td>
                    <td className="px-3 py-3">{notification.diagnostics ?? '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </AppPage>
  );
};

export default AlertsPage;
