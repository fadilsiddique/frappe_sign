// Draws a zigzag signature on the guest page's signature pad.
import { expect, type Page } from '@playwright/test'

export async function drawSignature(page: Page) {
  const pad = page.getByTestId('pad')
  await expect(pad).toBeVisible()
  // The sheet slides up from below the screen. A box read before or during the slide puts the
  // stroke below the pad, on the footer or the backdrop. Wait until the pad is fully on screen and
  // has stopped moving.
  const screenHeight = page.viewportSize()!.height
  let box = (await pad.boundingBox())!
  await expect(async () => {
    const settled = (await pad.boundingBox())!
    const moved = settled.y !== box.y
    box = settled
    expect(box.y + box.height).toBeLessThanOrEqual(screenHeight)
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
