// Place the guide in the corner that covers the least highlighted content.
export function tutorialDockPosition(rect, width, height) {
  const vw = rect.viewportWidth, vh = rect.viewportHeight
  const gap = vw > 720 ? 20 : 12
  const right = Math.max(gap, vw - width - gap)
  const bottom = Math.max(gap, vh - height - gap)
  const positions = vw > 720
    ? [{ left: right, top: bottom }, { left: gap, top: bottom }, { left: right, top: gap }, { left: gap, top: gap }]
    : [{ left: right, top: bottom }, { left: right, top: gap }]
  const overlap = p => Math.max(0, Math.min(p.left + width, rect.right) - Math.max(p.left, rect.left))
    * Math.max(0, Math.min(p.top + height, rect.bottom) - Math.max(p.top, rect.top))
  return positions.reduce((best, p) => overlap(p) < overlap(best) ? p : best)
}
