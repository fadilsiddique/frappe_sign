// Shared by the U.13 quality specs: run axe-core (WCAG A and AA) and list serious findings.
import { readFileSync } from 'node:fs'
import type { Page } from '@playwright/test'

const AXE = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8')

export async function axeFindings(page: Page): Promise<string[]> {
  await page.evaluate(AXE)
  return page.evaluate(async () => {
    // @ts-expect-error axe is injected above
    const result = await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa'] })
    return result.violations
      .filter((v: { impact: string }) => v.impact === 'serious' || v.impact === 'critical')
      .map(
        (v: { id: string; nodes: { target: string[]; html: string }[] }) =>
          `${v.id}: ${v.nodes
            .slice(0, 3)
            .map((n) => n.target.join(' ') + ' ' + n.html.slice(0, 140))
            .join(' | ')}`,
      )
  })
}
