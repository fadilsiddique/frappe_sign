// Draws a zigzag signature on the guest page's signature pad.
import { expect, type Page } from '@playwright/test'

export async function drawSignature(page: Page) {
  const pad = page.getByTestId('pad')
  await expect(pad).toBeVisible()
  // The sheet slides up; a box read mid-slide puts the stroke below the pad, on the backdrop,
  // which closes the sheet. Wait until the pad stops moving.
  let box = (await pad.boundingBox())!
  await expect(async () => {
    const settled = (await pad.boundingBox())!
    const moved = settled.y !== box.y
    box = settled
    expect(moved).toBe(false)
  }).toPass({ intervals: [100] })
  const points = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9].map((x, i) => ({
    x: box.x + box.width * x,
    y: box.y + box.height * (i % 2 ? 0.35 : 0.7),
  }))
  await page.mouse.move(points[0].x, points[0].y)
  await page.mouse.down()
  for (const point of points.slice(1)) await page.mouse.move(point.x, point.y, { steps: 6 })
  await page.mouse.up()
}
