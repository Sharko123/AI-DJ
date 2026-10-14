"""Self-contained HTML histogram shared by the plot_*.py scripts."""
from html import escape

W, H = 960, 420  # SVG viewBox
ML, MR, MT, MB = 56, 16, 28, 52


def write_histogram(out, counts, labels, x_ticks, *, page_title, title, subtitle,
                    x_label, column, marker=None, overflow=None):
    """Write a one-series histogram page.

    counts/labels: one entry per bin. x_ticks: (position in bins, text) pairs.
    marker: optional (position in bins, text) for a dashed reference line.
    overflow: tick text for the last bin when it is an open-ended catch-all;
    that bin is then drawn after a visual break.
    """
    n = sum(counts)
    y_step = next(s for s in (25, 50, 100, 200, 250, 500, 1000, 2000, 5000) if max(counts) / s <= 6)
    y_max = -(-max(counts) // y_step) * y_step
    plot_w, plot_h = W - ML - MR, H - MT - MB
    gap = 28  # visual break before the overflow bin
    slot = (plot_w - (gap if overflow else 0)) / len(counts)

    def x_of(i):
        return ML + i * slot + (gap if overflow and i == len(counts) - 1 else 0)

    def y_of(c):
        return MT + plot_h * (1 - c / y_max)

    svg = []
    for c in range(0, y_max + 1, y_step):
        y = y_of(c)
        svg.append(f'<line class="grid" x1="{ML}" x2="{W - MR}" y1="{y:.1f}" y2="{y:.1f}"/>')
        svg.append(f'<text class="tick" x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end">{c}</text>')
    for i, c in enumerate(counts):
        x, y = x_of(i) + 1, y_of(c)
        h = MT + plot_h - y
        r = min(2, h)
        tip = f"{labels[i]}: {c} transitions ({100 * c / n:.1f}%)"
        svg.append(
            f'<path class="bar" data-tip="{escape(tip)}" d="M{x:.1f},{MT + plot_h} v{-(h - r):.1f} '
            f'q0,{-r} {r},{-r} h{slot - 2 - 2 * r:.1f} q{r},0 {r},{r} v{h - r:.1f} z"/>')
        # Full-height hit target so short bars are still hoverable.
        svg.append(f'<rect class="hit" data-tip="{escape(tip)}" x="{x_of(i):.1f}" y="{MT}" '
                   f'width="{slot:.1f}" height="{plot_h}"/>')
    base = MT + plot_h
    svg.append(f'<line class="axis" x1="{ML}" x2="{W - MR}" y1="{base}" y2="{base}"/>')
    for pos, text in x_ticks:
        x = ML + pos * slot
        svg.append(f'<text class="tick" x="{x:.1f}" y="{base + 18}" text-anchor="middle">{text}</text>')
    if overflow:
        x_over = x_of(len(counts) - 1) + slot / 2
        svg.append(f'<text class="tick" x="{x_over:.1f}" y="{base + 18}" text-anchor="middle">{overflow}</text>')
    svg.append(f'<text class="label" x="{ML + plot_w / 2}" y="{H - 8}" text-anchor="middle">{x_label}</text>')
    svg.append(f'<text class="label" x="{ML - 44}" y="{MT - 12}">Transitions</text>')
    if marker:
        xm = ML + marker[0] * slot
        svg.append(f'<line class="median" x1="{xm:.1f}" x2="{xm:.1f}" y1="{MT}" y2="{base}"/>')
        svg.append(f'<text class="note" x="{xm + 6:.1f}" y="{MT + 10}">{marker[1]}</text>')

    rows = "".join(f"<tr><td>{escape(l)}</td><td>{c}</td></tr>" for l, c in zip(labels, counts))
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(page_title)}</title>
<style>
  :root {{ --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e;
           --grid: #e4e3df; --series: #2a78d6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7;
             --grid: #383835; --series: #3987e5; }}
  }}
  body {{ margin: 0; padding: 24px 16px; background: var(--page); color: var(--ink);
          font: 14px/1.4 system-ui, sans-serif; }}
  main {{ max-width: 1000px; margin: 0 auto; background: var(--surface); padding: 20px;
          border-radius: 8px; position: relative; }}
  h1 {{ font-size: 18px; margin: 0 0 4px; }}
  p {{ margin: 0 0 12px; color: var(--ink2); }}
  svg {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .axis {{ stroke: var(--ink2); stroke-width: 1; }}
  .bar {{ fill: var(--series); }}
  .hit {{ fill: transparent; }}
  .tick, .label, .note {{ fill: var(--ink2); font-size: 12px; }}
  .note {{ fill: var(--ink); }}
  .median {{ stroke: var(--ink); stroke-width: 1; stroke-dasharray: 4 3; }}
  #tip {{ position: fixed; pointer-events: none; background: var(--ink); color: var(--surface);
          padding: 4px 8px; border-radius: 4px; font-size: 12px; display: none; }}
  details {{ margin-top: 12px; color: var(--ink2); }}
  table {{ border-collapse: collapse; margin-top: 8px; }}
  td, th {{ padding: 2px 16px 2px 0; text-align: left; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<main>
  <h1>{escape(title)}</h1>
  <p>{escape(subtitle)}</p>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">
    {"".join(svg)}
  </svg>
  <details><summary>Data table</summary>
    <table><tr><th>{escape(column)}</th><th>Transitions</th></tr>{rows}</table>
  </details>
</main>
<div id="tip"></div>
<script>
  const tip = document.getElementById('tip');
  document.querySelectorAll('.hit').forEach(el => {{
    el.addEventListener('mousemove', e => {{
      tip.textContent = el.dataset.tip;
      tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + 'px';
      tip.style.top = (e.clientY - 32) + 'px';
    }});
    el.addEventListener('mouseleave', () => tip.style.display = 'none');
  }});
</script>
</body>
</html>
"""
    out.write_text(html)
