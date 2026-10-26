"""Render the frozen benchmark as editable SVG and PNG, without matplotlib.

Uses stdlib SVG generation; PNG requires Pillow (a rendering dependency only).
python benchmarks/plot.py --results benchmarks/results-v2 --output docs/assets

Reads evidence and verifies every published input against its frozen manifest.
Does not rewrite benchmark receipts. No numerical smoothing or invented trials.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path

COLORS = {'paper': '#f6f5ef', 'ink': '#242923', 'muted': '#5e665c',
          'line': '#d6d9cf', 'bar': '#8b958a', 'adaptive': '#31614a', 'learned-cost': '#b44831'}
WIDTH, HEIGHT = 1480, 900
FONT_CANDIDATES = [
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
]
BOLD_CANDIDATES = [
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
]


class Figure:
    """One geometry source for SVG and supersampled Pillow rendering."""
    def __init__(self):
        self.elements = []
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
                    '<title id="title">Controlled prepared-repair microbenchmark</title>',
                    '<desc id="desc">Measured policy results on nine held-out synthetic tasks from three cause families, repeated ten times. Adaptive and fixed three both resolve all tasks; the learned cost ranking does not improve on the heuristic. No live coding models were benchmarked.</desc>']

    def rectangle(self, x, y, width, height, fill):
        self.svg.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{width:.3f}" height="{height:.3f}" fill="{fill}"/>')
        self.elements.append(('rectangle', (x, y, x + width, y + height), fill))

    def line(self, x1, y1, x2, y2, color, width=1):
        self.svg.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{width}"/>')
        self.elements.append(('line', (x1, y1, x2, y2), color, width))

    def text(self, x, y, text, size=18, color=None, bold=False, anchor='start'):
        color = color or COLORS['ink']
        weight = '700' if bold else '400'
        self.svg.append(f'<text x="{x:.3f}" y="{y:.3f}" font-family="Arial,DejaVu Sans,sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{html.escape(text)}</text>')
        self.elements.append(('text', (x, y), text, size, color, bold, anchor))

    def save(self, svg_path, png_path):
        svg_path.write_text('\n'.join(self.svg + ['</svg>']) + '\n')
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise SystemExit('SVG rendered. PNG requires Pillow; use a Python environment with Pillow installed.')
        scale = 2
        image = Image.new('RGB', (WIDTH * scale, HEIGHT * scale), COLORS['paper'])
        draw = ImageDraw.Draw(image)
        regular = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
        bold = next((p for p in BOLD_CANDIDATES if Path(p).exists()), regular)
        if not regular:
            raise SystemExit('SVG rendered. PNG requires Arial, DejaVu Sans or Liberation Sans on this host.')
        fonts = {}
        for element in self.elements:
            kind = element[0]
            if kind == 'rectangle':
                _, coords, fill = element
                draw.rectangle(tuple(round(v * scale) for v in coords), fill=fill)
            elif kind == 'line':
                _, coords, color, width = element
                draw.line(tuple(round(v * scale) for v in coords), fill=color, width=max(1, round(width * scale)))
            else:
                _, (x, y), text, size, color, is_bold, anchor = element
                key = size, is_bold
                if key not in fonts:
                    fonts[key] = ImageFont.truetype(bold if is_bold else regular, round(size * scale))
                align = {'start': 'ls', 'middle': 'ms', 'end': 'rs'}[anchor]
                draw.text((round(x * scale), round(y * scale)), text, font=fonts[key], fill=color, anchor=align)
        image.save(png_path)


def verified_sources(directory):
    manifest_path = directory / 'artifact-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    sources = []
    for name in ('summary.json', 'additional-analysis.json', 'trials.jsonl'):
        path = directory / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest['files'][name]['sha256']:
            raise ValueError(f'Frozen source hash mismatch: {name}')
        sources.append({'path': path.as_posix(), 'sha256': digest, 'bytes': path.stat().st_size,
                        'public_url': 'https://github.com/nazeeh111/ForkSense/blob/main/' + path.as_posix()})
    return sources


def build(summary, extra):
    figure = Figure()
    c = COLORS
    figure.rectangle(0, 0, WIDTH, HEIGHT, c['paper'])
    figure.text(52, 55, 'FORKSENSE / EVALUATION', 16, c['muted'], True)
    figure.text(52, 108, 'Controlled prepared-repair microbenchmark', 34, bold=True)
    figure.text(52, 147, '9 held-out tasks  /  3 cause families  /  10 repeats  /  zero model calls', 21, c['muted'])
    figure.line(52, 175, WIDTH - 52, 175, c['line'])
    xs, widths, maxima = (310, 705, 1110), (240, 210, 210), (1., 3., .8)
    headers = ('Resolved', 'Commands', 'Summed process time')
    units = ('95% family bootstrap', 'mean per trial', 'seconds, mean per trial')
    for x, header, unit in zip(xs, headers, units):
        figure.text(x, 217, header, 22, bold=True)
        figure.text(x, 244, unit, 16, c['muted'])
    labels = {'single': 'Single attempt', 'fixed-3': 'Fixed 3, concurrent',
              'random': 'Random diagnostic', 'uncertainty': 'Information gain',
              'adaptive': 'Adaptive heuristic', 'learned-cost': 'Learned cost',
              'root-uct-proxy': 'Root UCT proxy'}
    policies = ('single', 'fixed-3', 'random', 'uncertainty', 'adaptive', 'learned-cost', 'root-uct-proxy')
    for index, name in enumerate(policies):
        row = summary['policies'][name]
        y = 294 + index * 58
        color = c.get(name, c['bar'])
        figure.text(52, y + 7, labels[name], 21, bold=name in ('adaptive', 'learned-cost'))
        vals = (row['resolution_rate'], row['mean_command_calls'], row['mean_subprocess_seconds'])
        for panel, (x, width, maximum, value) in enumerate(zip(xs, widths, maxima, vals)):
            figure.rectangle(x, y - 17, width, 25, '#e6e8df')
            figure.rectangle(x, y - 17, width * value / maximum, 25, color)
            text = f'{value:.0%}' if panel == 0 else (f'{value:.2f}' if panel == 1 else f'{value:.3f}')
            figure.text(x + width + 12, y + 4, text, 19)
        low, high = row['resolution_family_cluster_bootstrap_95']
        x = xs[0]; width = widths[0]
        figure.line(x + low * width, y - 4, x + high * width, y - 4, c['ink'], 2)
        figure.line(x + low * width, y - 10, x + low * width, y + 2, c['ink'], 2)
        figure.line(x + high * width, y - 10, x + high * width, y + 2, c['ink'], 2)
    axis_y = 686
    for panel, (x, width, maximum) in enumerate(zip(xs, widths, maxima)):
        figure.line(x, axis_y, x + width, axis_y, c['muted'])
        for tick in (0., .5, 1.):
            v = maximum * tick
            figure.line(x + width * tick, axis_y, x + width * tick, axis_y + 5, c['muted'])
            label = f'{v:.0%}' if panel == 0 else (f'{v:g}' if panel == 1 else f'{v:.1f}')
            figure.text(x + width * tick, axis_y + 27, label, 16, c['muted'], anchor='middle')
    figure.line(52, 739, WIDTH - 52, 739, c['line'])
    delta = extra['trajectory_checks']['learned-cost_vs_adaptive']['mean_wall_difference']
    overhead = summary['setup_costs']['learned_cost_training_subprocess_seconds']
    figure.text(52, 777, 'Learned ranking did not beat the heuristic.', 23, c['learned-cost'], True)
    figure.text(52, 808, f'Equal resolution and commands; +{delta:.3f} s/trial wall time on this host, plus {overhead:.2f} s training.', 20)
    figure.text(52, 846, 'Prepared repairs and oracle-informed forecasts. Only three bootstrap clusters. No established coding-agent improvement.', 18, c['muted'])
    figure.text(52, 875, 'Costs include actual probe + verification subprocesses; per-trial bars exclude one-time setup. See benchmark methodology and receipts.', 17, c['muted'])
    return figure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('benchmarks/results-v2'))
    parser.add_argument('--output', type=Path, default=Path('docs/assets'))
    args = parser.parse_args(argv)
    sources = verified_sources(args.results)
    summary = json.loads((args.results / 'summary.json').read_text())
    extra = json.loads((args.results / 'additional-analysis.json').read_text())
    if summary['seeds'] != 10 or any(r['unique_tasks'] != 9 for r in summary['policies'].values()):
        raise ValueError('This labeled layout expects the frozen 9-task, 10-repeat run')
    args.output.mkdir(parents=True, exist_ok=True)
    svg_path = args.output / 'benchmarks.svg'; png_path = args.output / 'benchmarks.png'
    if svg_path.exists() or png_path.exists():
        parser.error('figure already exists; render to a fresh output folder to preserve valid artifacts')
    build(summary, extra).save(svg_path, png_path)
    outputs = [{'path': path.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'bytes': path.stat().st_size,
                'public_url': 'https://github.com/nazeeh111/ForkSense/blob/main/' + path.as_posix()}
               for path in (svg_path, png_path)]
    (args.output / 'benchmarks.sources.json').write_text(json.dumps({
        'verified_against': (args.results / 'artifact-manifest.json').as_posix(),
        'inputs': sources, 'outputs': outputs,
        'generator': 'benchmarks/plot.py',
        'public_generator_url': 'https://github.com/nazeeh111/ForkSense/blob/main/benchmarks/plot.py',
        'note': 'Paths are exact release artifact paths; public availability must be verified after publication.',
    }, indent=2) + '\n')
    print(svg_path); print(png_path)


if __name__ == '__main__':
    main()
