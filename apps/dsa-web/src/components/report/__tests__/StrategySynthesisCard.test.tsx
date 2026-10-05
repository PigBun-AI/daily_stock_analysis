import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReportLanguage, StrategySynthesis } from '../../../types/analysis';
import { StrategySynthesisCard } from '../StrategySynthesisCard';

const dissent = {
  skillId: 'growth_quality', signal: 'sell' as const, confidence: 0.8,
  reasoning: 'Earnings growth is slowing. Cash-flow conversion needs confirmation.', conditionsMet: ['Earnings reviewed'],
};
const synthesis: StrategySynthesis = {
  finalSignal: 'buy', consensusLevel: 'low', conflictCount: 1, conflictSeverity: 'high', confidence: 0.7,
  summaryParams: { opinionCount: 3, invalidOpinionCount: 1 },
  signalDistribution: {
    bullish: { count: 1, weightShare: 0.5 }, neutral: { count: 1, weightShare: 0.3 }, bearish: { count: 1, weightShare: 0.2 },
  },
  supportingSkills: [{ ...dissent, skillId: 'trend', signal: 'buy', reasoning: 'Trend intact' }],
  opposingSkills: [dissent], primaryDissent: dissent,
  conflicts: [{ conflictType: 'directional_opposition', severity: 'high', participants: ['trend', 'growth_quality'] }],
  deliberation: { rounds: 1, summary: { resolutionStatus: 'partially_resolved', confidenceAdjustment: -0.06, unresolvedConflictTypes: [] } },
  revisionProjection: {
    mode: 'preview_only', finalSignalOverridden: false, projectedSignal: 'hold', projectedConfidence: 0.6,
    projectedConflictSeverity: 'low', projectedConflictCount: 1,
  },
};

describe('StrategySynthesisCard', () => {
  it('omits the card for absent historical or single-agent evidence', () => {
    const { container } = render(<StrategySynthesisCard />);
    expect(container).toBeEmptyDOMElement();
  });

  it.each([
    ['zh', '多策略共识', '协同推演预览，不改变策略综合信号', '买入'],
    ['en', 'Strategy consensus', 'Deliberation preview; does not change the strategy synthesis signal', 'Buy'],
    ['ko', '다중 전략 합의', '협의 시뮬레이션 미리보기이며 전략 종합 신호를 변경하지 않습니다', '매수'],
  ] as const)('renders %s synthesis and labels the distinct preview', (language, title, preview, finalSignal) => {
    const { container } = render(<StrategySynthesisCard synthesis={synthesis} language={language as ReportLanguage} />);
    expect(screen.getByText(title)).toBeVisible();
    expect(screen.getByText('50.0%')).toBeVisible();
    expect(screen.getByText(finalSignal, { exact: true })).toBeVisible();
    expect(screen.getAllByText('growth_quality', { exact: true, selector: 'span' })[0]).toBeVisible();
    const panel = container.querySelector('details:last-of-type');
    expect(panel).not.toHaveAttribute('open');
    // Outer disclosure exposes the preview; no frontend vote recomputation.
    const outer = Array.from(container.querySelectorAll('details')).find(element => element.querySelector('h3')?.textContent?.includes(language === 'zh' ? '支持' : language === 'en' ? 'Supporting' : '지지'));
    expect(outer).toBeDefined();
    fireEvent.click(outer!.querySelector('summary')!);
    expect(outer).toHaveAttribute('open');
    expect(screen.getByText(preview)).toBeVisible();
    expect(screen.getByText(finalSignal, { exact: true })).toBeVisible();
  });

  it('preserves absent distribution and zero-weight uncertainty instead of displaying fake votes', () => {
    const { rerender } = render(<StrategySynthesisCard synthesis={{ ...synthesis, signalDistribution: null, primaryDissent: null }} />);
    expect(screen.queryByText('有效策略权重占比')).not.toBeInTheDocument();
    expect(screen.queryByText('主要反对观点')).not.toBeInTheDocument();
    rerender(<StrategySynthesisCard synthesis={{
      ...synthesis, consensusLevel: 'insufficient', signalDistribution: {
        bullish: { count: 0, weightShare: null }, neutral: { count: 0, weightShare: null }, bearish: { count: 0, weightShare: null },
      }, supportingSkills: [], opposingSkills: [], primaryDissent: null,
    }} />);
    expect(screen.getByText('有效证据不足，无法形成可靠共识。')).toBeVisible();
    expect(screen.getAllByText('未记录').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
  });

  it('truncates long reasoning in the disclosure and allows expansion', () => {
    const long = 'Verified earnings context. '.repeat(100);
    const { container } = render(<StrategySynthesisCard synthesis={{ ...synthesis, primaryDissent: { ...dissent, reasoning: long } }} />);
    const opinion = container.querySelector('details')!;
    expect(opinion).not.toHaveAttribute('open');
    expect(opinion.querySelector('summary .line-clamp-2')).toHaveTextContent(long.trim());
    fireEvent.click(opinion.querySelector('summary')!);
    expect(opinion).toHaveAttribute('open');
    expect(opinion.querySelector('p')).toBeVisible();
  });
});
