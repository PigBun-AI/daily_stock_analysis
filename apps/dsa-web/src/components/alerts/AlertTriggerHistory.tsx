import type React from 'react';
import { Activity } from 'lucide-react';
import { Badge, Card, EmptyState, Loading } from '../common';
import type { AlertTriggerItem } from '../../types/alerts';
import { formatDateTime } from '../../utils/format';
import { getMarketPhaseSummaryLabel } from '../../utils/marketPhase';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiTextKey } from '../../i18n/uiText';

const STATUS_KEYS: Record<string, UiTextKey> = {
  triggered: 'alerts.trigger.triggered',
  skipped: 'alerts.trigger.skipped',
  degraded: 'alerts.trigger.degraded',
  failed: 'alerts.trigger.failed',
};

function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'triggered') return 'success';
  if (status === 'skipped' || status === 'degraded') return 'warning';
  if (status === 'failed') return 'danger';
  return 'default';
}

function formatNullable(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '--';
  return String(value);
}

interface AlertTriggerHistoryProps {
  triggers: AlertTriggerItem[];
  isLoading?: boolean;
}

export const AlertTriggerHistory: React.FC<AlertTriggerHistoryProps> = ({ triggers, isLoading = false }) => {
  const { language, t } = useUiLanguage();
  const phasePrefix = language === 'en' ? 'Market phase' : '市场阶段';

  const renderPhaseQuality = (trigger: AlertTriggerItem): React.ReactNode => {
    const phase = getMarketPhaseSummaryLabel(trigger.marketPhaseSummary, language);
    const quality = trigger.analysisContextPackOverview?.dataQuality?.level;
    const limitations = trigger.analysisContextPackOverview?.dataQuality?.limitations?.slice(0, 2) ?? [];
    if (!phase && !quality && limitations.length === 0) {
      return <span className="text-xs text-muted-text">--</span>;
    }
    const phaseLabel = phase
      ? phase.replace(`${phasePrefix}: `, '').replace(`${phasePrefix}：`, '')
      : null;
    return (
      <div className="space-y-1">
        {phaseLabel ? <Badge variant="default">{phaseLabel}</Badge> : null}
        {quality ? <div className="text-xs text-secondary-text">{t('alerts.qualityLabel', { quality })}</div> : null}
        {limitations.length ? (
          <div className="max-w-[180px] text-xs text-muted-text">{limitations.join(language === 'en' ? '; ' : '；')}</div>
        ) : null}
      </div>
    );
  };

  return (
    <Card title={t('alerts.triggersTitle')} subtitle={t('alerts.triggersSubtitle')} variant="bordered" padding="md">
      {isLoading ? <Loading label={t('alerts.triggersLoading')} /> : null}
      {!isLoading && triggers.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-6 w-6" />}
          title={t('alerts.triggersEmptyTitle')}
          description={t('alerts.triggersEmptyDescription')}
        />
      ) : null}
      {!isLoading && triggers.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-border/60 text-xs font-medium text-muted-text">
              <tr>
                <th className="px-3 py-2 font-medium">{t('alerts.colStatus')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colPhaseQuality')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colTarget')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colObserved')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colThreshold')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colDataSource')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colDataTime')}</th>
                <th className="px-3 py-2 font-medium">{t('alerts.colReason')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {triggers.map((trigger) => (
                <tr key={trigger.id} className="align-top">
                  <td className="px-3 py-3">
                    <Badge variant={statusVariant(trigger.status)}>
                      {STATUS_KEYS[trigger.status] ? t(STATUS_KEYS[trigger.status]) : trigger.status}
                    </Badge>
                  </td>
                  <td className="px-3 py-3">{renderPhaseQuality(trigger)}</td>
                  <td className="px-3 py-3 font-mono text-secondary-text">{trigger.target}</td>
                  <td className="px-3 py-3 text-secondary-text">{formatNullable(trigger.observedValue)}</td>
                  <td className="px-3 py-3 text-secondary-text">{formatNullable(trigger.threshold)}</td>
                  <td className="px-3 py-3 text-secondary-text">{formatNullable(trigger.dataSource)}</td>
                  <td className="px-3 py-3 text-xs text-secondary-text">
                    {formatDateTime(trigger.dataTimestamp ?? trigger.triggeredAt)}
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    {trigger.reason || trigger.diagnostics || '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Card>
  );
};
