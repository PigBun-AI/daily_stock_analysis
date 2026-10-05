import { expect, test } from '@playwright/test';

// Invented evidence exercises real API conversion and ReportSummary composition.
const opinion = (skill: string, signal: string, confidence: number, reasoning: string) => ({
  skill_id: skill, agent_name: `skill_${skill}`, signal, confidence, reasoning, conditions_met: [],
});
const bull = opinion('trend', 'buy', 0.8, 'Price trend is supported by verified market data.');
const bear = opinion('growth_quality', 'sell', 0.85, 'Earnings growth has slowed. Operating cash-flow conversion requires confirmation.');
const neutral = opinion('value', 'hold', 0.7, 'Current valuation leaves limited margin of safety.');
const synthesis = {
  schema_version: 'strategy-synthesis-v1', final_signal: 'buy', weighted_score: 3.6,
  confidence: 0.65, original_confidence: 0.8, consensus_level: 'low', conflict_count: 1, conflict_severity: 'high',
  summary_params: { opinion_count: 3, total_opinion_count: 4, invalid_opinion_count: 1 },
  signal_distribution: {
    bullish: { count: 1, weight_share: 0.5 }, neutral: { count: 1, weight_share: 0.2 }, bearish: { count: 1, weight_share: 0.3 },
  },
  supporting_skills: [bull], opposing_skills: [bear, neutral], primary_dissent: bear,
  conflicts: [{ conflict_type: 'directional_opposition', severity: 'high', participants: ['trend', 'growth_quality'] }],
  deliberation: { status: 'completed', mode: 'mediator_v0', rounds: 1,
    summary: { resolution_status: 'partially_resolved', confidence_adjustment: -0.06, unresolved_conflict_types: ['directional_opposition'] } },
  revision_projection: { mode: 'preview_only', final_signal_overridden: false, projected_signal: 'hold',
    projected_confidence: 0.6, projected_conflict_count: 1, projected_conflict_severity: 'medium', projected_consensus_level: 'medium' },
};

for (const [language, theme, width] of [
  ['zh', 'dark', 1280], ['zh', 'light', 390], ['en', 'dark', 390], ['ko', 'light', 1280],
] as const) {
  test(`strategy synthesis: ${language} ${theme} ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1400 });
    await page.route('**/api/v1/history/101', route => route.fulfill({ json: {
      meta: { query_id: 'fixture', stock_code: '600519', stock_name: 'Example Company', report_type: 'detailed',
        report_language: language, created_at: '2026-10-05T09:00:00', current_price: 100, change_pct: 0 },
      summary: { analysis_summary: 'Verify earnings and price evidence before acting.',
        operation_advice: 'Hold', sentiment_score: 65, trend_prediction: 'Mixed evidence' },
      strategy: { ideal_buy: '98', stop_loss: '92', take_profit: '110' }, details: { strategy_synthesis: synthesis },
    } }));
    await page.route('**/src/main.tsx', route => route.fulfill({
      contentType: 'application/javascript', body: `
        import React from '/node_modules/.vite/deps/react.js';
        import ReactDOMClient from '/node_modules/.vite/deps/react-dom_client.js';
        import '/src/index.css';
        import { ReportSummary } from '/src/components/report/ReportSummary.tsx';
        import { historyApi } from '/src/api/history.ts';
        document.documentElement.classList.toggle('dark', ${JSON.stringify(theme === 'dark')});
        function Fixture() {
          const [report, setReport] = React.useState(null);
          const [show, setShow] = React.useState(false);
          React.useEffect(() => { historyApi.getDetail(101).then(setReport); }, []);
          if (!report) return null;
          return React.createElement('main', {className:'mx-auto max-w-4xl p-4'},
            React.createElement('button', {onClick:()=>setShow(true)}, 'Show synthesis'),
            React.createElement(ReportSummary, {data:{...report, details:show?report.details:undefined}}));
        }
        ReactDOMClient.createRoot(document.getElementById('root')).render(React.createElement(Fixture));
      `,
    }));
    await page.goto('/');
    await expect(page.getByText('Example Company', { exact: true })).toBeVisible();
    if (language === 'zh' && theme === 'dark') {
      const before = testInfo.outputPath('strategy-synthesis-before.png');
      await page.screenshot({ path: before, fullPage: true, animations: 'disabled' });
      await testInfo.attach('before', { path: before, contentType: 'image/png' });
    }
    await page.getByRole('button', { name: 'Show synthesis' }).click();
    const titles = { zh: '多策略共识', en: 'Strategy consensus', ko: '다중 전략 합의' };
    await expect(page.getByText(titles[language], { exact: true })).toBeVisible();
    await expect(page.getByText('50.0%', { exact: true })).toBeVisible();
    await expect(page.getByText('growth_quality', { exact: true }).first()).toBeVisible();
    const outer = page.locator('details').filter({ has: page.locator('section') }).first();
    await outer.locator(':scope > summary').click();
    const previews = {
      zh: '协同推演预览，不改变策略综合信号',
      en: 'Deliberation preview; does not change the strategy synthesis signal',
      ko: '협의 시뮬레이션 미리보기이며 전략 종합 신호를 변경하지 않습니다',
    };
    await expect(page.getByText(previews[language], { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const after = testInfo.outputPath(`strategy-synthesis-${language}-${theme}-${width}.png`);
    await page.screenshot({ path: after, fullPage: true, animations: 'disabled' });
    await testInfo.attach('after', { path: after, contentType: 'image/png' });
  });
}
