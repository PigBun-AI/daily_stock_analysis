import type { ReportLanguage, StrategyDisplayOpinion, StrategySynthesis } from '../../types/analysis';
import { normalizeReportLanguage } from '../../utils/reportLanguage';
import { Badge, Card } from '../common';
import { DashboardPanelHeader } from '../dashboard';

const TEXT = {
  zh: {
    eyebrow: '策略观点', title: '多策略共识', signal: '策略综合信号', consensus: '共识度',
    conflict: '策略分歧', valid: '有效策略', invalid: '无效策略', confidence: '观点置信度',
    weights: '有效策略权重占比', dissent: '主要反对观点', supporting: '支持综合信号',
    opposing: '反对综合信号', details: '查看策略与分歧详情', none: '无', unknown: '未记录',
    insufficient: '有效证据不足，无法形成可靠共识。',
    caveat: '策略分歧不等于风控风险等级；最终报告建议仍受独立风控约束。',
    preview: '协同推演预览，不改变策略综合信号', deliberation: '协同讨论', rounds: '轮数',
    adjusted: '置信度调整（百分点）',
    signals: { strong_buy: '强烈买入', buy: '买入', hold: '观望', sell: '卖出', strong_sell: '强烈卖出' },
    levels: { insufficient: '证据不足', none: '无', low: '低', medium: '中', high: '高' },
    sides: { bullish: '看多', neutral: '中性', bearish: '看空' },
    conflicts: {
      directional_opposition: '多空方向相反', wide_score_dispersion: '策略评分分歧',
      high_confidence_dissent: '高置信度少数派反对', adjustment_contradiction: '评分调整相反',
    },
    resolutions: { resolved: '已收敛', partially_resolved: '部分收敛', unresolved: '未收敛' },
  },
  en: {
    eyebrow: 'STRATEGY OPINIONS', title: 'Strategy consensus', signal: 'Strategy synthesis signal', consensus: 'Consensus',
    conflict: 'Strategy disagreement', valid: 'Valid strategies', invalid: 'Invalid strategies', confidence: 'Opinion confidence',
    weights: 'Share of valid strategy weights', dissent: 'Primary dissent', supporting: 'Supporting the synthesis',
    opposing: 'Opposing the synthesis', details: 'View strategies and disagreements', none: 'None', unknown: 'Not recorded',
    insufficient: 'Insufficient valid evidence for reliable consensus.',
    caveat: 'Strategy disagreement is separate from risk severity. Independent risk controls still govern the final report advice.',
    preview: 'Deliberation preview; does not change the strategy synthesis signal', deliberation: 'Deliberation', rounds: 'Rounds',
    adjusted: 'Confidence adjustment (pp)',
    signals: { strong_buy: 'Strong buy', buy: 'Buy', hold: 'Hold', sell: 'Sell', strong_sell: 'Strong sell' },
    levels: { insufficient: 'Insufficient', none: 'None', low: 'Low', medium: 'Medium', high: 'High' },
    sides: { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' },
    conflicts: {
      directional_opposition: 'Opposing directions', wide_score_dispersion: 'Dispersed strategy scores',
      high_confidence_dissent: 'High-confidence dissent', adjustment_contradiction: 'Opposing score adjustments',
    },
    resolutions: { resolved: 'Resolved', partially_resolved: 'Partially resolved', unresolved: 'Unresolved' },
  },
  ko: {
    eyebrow: '전략 의견', title: '다중 전략 합의', signal: '전략 종합 신호', consensus: '합의 수준',
    conflict: '전략 이견', valid: '유효 전략', invalid: '무효 전략', confidence: '의견 신뢰도',
    weights: '유효 전략 가중치 비중', dissent: '주요 반대 의견', supporting: '종합 신호 지지',
    opposing: '종합 신호 반대', details: '전략 및 이견 상세 보기', none: '없음', unknown: '기록 없음',
    insufficient: '신뢰할 수 있는 합의를 위한 유효 근거가 부족합니다.',
    caveat: '전략 이견은 위험 등급과 다릅니다. 최종 보고서 의견에는 독립적 위험 통제가 적용됩니다.',
    preview: '협의 시뮬레이션 미리보기이며 전략 종합 신호를 변경하지 않습니다', deliberation: '협의', rounds: '횟수',
    adjusted: '신뢰도 조정(퍼센트포인트)',
    signals: { strong_buy: '강력 매수', buy: '매수', hold: '관망', sell: '매도', strong_sell: '강력 매도' },
    levels: { insufficient: '근거 부족', none: '없음', low: '낮음', medium: '보통', high: '높음' },
    sides: { bullish: '상승', neutral: '중립', bearish: '하락' },
    conflicts: {
      directional_opposition: '상반된 방향', wide_score_dispersion: '전략 점수 이견',
      high_confidence_dissent: '높은 신뢰도의 반대 의견', adjustment_contradiction: '상반된 점수 조정',
    },
    resolutions: { resolved: '해결', partially_resolved: '부분 해결', unresolved: '미해결' },
  },
};

interface Props { synthesis?: StrategySynthesis | null; language?: ReportLanguage }

export function StrategySynthesisCard({ synthesis, language = 'zh' }: Props) {
  if (!synthesis) return null;
  const text = TEXT[normalizeReportLanguage(language)];
  const percent = (value?: number | null) => value == null ? text.unknown : `${(value * 100).toFixed(1)}%`;
  const points = (value?: number | null) => value == null ? text.unknown : `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}`;
  const level = (value?: string | null) => text.levels[value as keyof typeof text.levels] ?? text.unknown;
  const signal = (value: string) => text.signals[value as keyof typeof text.signals] ?? text.unknown;
  const conflictLabel = (value: string) => text.conflicts[value as keyof typeof text.conflicts] ?? text.conflict;
  const renderOpinion = (opinion: StrategyDisplayOpinion, index: number) => (
    <details key={`${opinion.skillId}-${index}`} className="home-subpanel min-w-0 rounded-lg p-3">
      <summary className="cursor-pointer text-sm">
        <span className="break-words font-medium">{opinion.skillId}</span>
        {' · '}{signal(opinion.signal)}{' · '}{text.confidence}: {percent(opinion.confidence)}
        {opinion.reasoning && <span className="mt-1 line-clamp-2 text-xs text-muted-text">{opinion.reasoning}</span>}
      </summary>
      {opinion.reasoning && <p className="mt-2 whitespace-pre-wrap break-words text-sm">{opinion.reasoning}</p>}
      {opinion.conditionsMet.length > 0 && <ul className="mt-2 list-inside list-disc text-xs text-muted-text">
        {opinion.conditionsMet.map((condition, i) => <li key={i}>{condition}</li>)}
      </ul>}
    </details>
  );

  return (
    <Card variant="bordered" padding="md" className="home-panel-card min-w-0 text-left">
      <DashboardPanelHeader eyebrow={text.eyebrow} title={text.title} className="mb-3" />
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-xs text-muted-text">{text.signal}</dt><dd>{signal(synthesis.finalSignal)}</dd></div>
        <div><dt className="text-xs text-muted-text">{text.consensus}</dt><dd>{level(synthesis.consensusLevel)}</dd></div>
        <div><dt className="text-xs text-muted-text">{text.conflict}</dt><dd>
          <Badge variant={synthesis.conflictSeverity === 'high' ? 'warning' : 'default'}>
            {level(synthesis.conflictSeverity)} · {synthesis.conflictCount ?? text.unknown}
          </Badge>
        </dd></div>
        <div><dt className="text-xs text-muted-text">{text.valid}</dt><dd>{synthesis.summaryParams?.opinionCount ?? text.unknown}</dd></div>
        <div><dt className="text-xs text-muted-text">{text.invalid}</dt><dd>{synthesis.summaryParams?.invalidOpinionCount ?? text.unknown}</dd></div>
        <div><dt className="text-xs text-muted-text">{text.confidence}</dt><dd>{percent(synthesis.confidence)}</dd></div>
      </dl>
      {synthesis.consensusLevel === 'insufficient' && <p className="mt-3 text-sm text-muted-text">{text.insufficient}</p>}
      {synthesis.signalDistribution && <div className="mt-4">
        <p className="mb-2 text-xs text-muted-text">{text.weights}</p>
        <div className="grid grid-cols-3 gap-2 text-sm">
          {(['bullish', 'neutral', 'bearish'] as const).map(side => <div key={side} className="home-subpanel rounded-lg p-2">
            <p>{text.sides[side]} · {synthesis.signalDistribution![side].count}</p>
            <p className="text-xs text-muted-text">{percent(synthesis.signalDistribution![side].weightShare)}</p>
          </div>)}
        </div>
      </div>}
      {synthesis.primaryDissent && <div className="mt-4 space-y-2">
        <h3 className="text-sm font-semibold">{text.dissent}</h3>
        {renderOpinion(synthesis.primaryDissent, 0)}
      </div>}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm text-muted-text">{text.details}</summary>
        <div className="mt-3 space-y-3">
          {([['supporting', synthesis.supportingSkills], ['opposing', synthesis.opposingSkills]] as const).map(([side, opinions]) => (
            <section key={side} className="space-y-2">
              <h3 className="text-sm font-semibold">{text[side]}</h3>
              {opinions.length ? opinions.map(renderOpinion) : <p className="text-xs text-muted-text">{text.none}</p>}
            </section>
          ))}
          {synthesis.conflicts.map((conflict, index) => <p key={index} className="break-words text-xs">
            {conflictLabel(conflict.conflictType)} · {level(conflict.severity)} · {conflict.participants.join(', ')}
          </p>)}
          {synthesis.deliberation && <section className="home-subpanel rounded-lg p-3 text-sm">
            <h3 className="font-semibold">{text.deliberation}</h3>
            <p>{text.rounds}: {synthesis.deliberation.rounds ?? text.unknown}</p>
            <p>{text.resolutions[synthesis.deliberation.summary?.resolutionStatus as keyof typeof text.resolutions] ?? text.unknown}</p>
            <p>{text.adjusted}: {points(synthesis.deliberation.summary?.confidenceAdjustment)}</p>
            {synthesis.deliberation.summary?.unresolvedConflictTypes.map((type, index) => <p key={index}>{conflictLabel(type)}</p>)}
          </section>}
          {synthesis.revisionProjection && <section className="home-subpanel rounded-lg p-3 text-sm">
            <h3 className="font-semibold">{text.preview}</h3>
            <p>{signal(synthesis.revisionProjection.projectedSignal)} · {text.confidence}: {percent(synthesis.revisionProjection.projectedConfidence)}</p>
            <p>{text.consensus}: {level(synthesis.revisionProjection.projectedConsensusLevel)}</p>
            <p>{text.conflict}: {level(synthesis.revisionProjection.projectedConflictSeverity)} · {synthesis.revisionProjection.projectedConflictCount ?? text.unknown}</p>
          </section>}
        </div>
      </details>
      <p className="mt-3 text-xs text-muted-text">{text.caveat}</p>
    </Card>
  );
}
