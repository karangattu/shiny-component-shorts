"""Offline GitHub syntax highlighting with bslib Shiny typography."""
from __future__ import annotations

import base64
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
HIGHLIGHT = ASSETS / 'highlightjs'


def font_css() -> str:
    """Embed the preset fonts so captures never fall back during offline renders."""
    return ''.join(
        f"@font-face{{font-family:'{family}';font-weight:300 800;src:url(data:font/woff2;base64,"
        + base64.b64encode((ASSETS / 'fonts' / file).read_bytes()).decode()
        + ") format('woff2');}"
        for family, file in [('Open Sans', 'OpenSans-Latin.woff2'), ('Source Code Pro', 'SourceCodePro-Latin.woff2')]
    )


def stylesheet() -> str:
    """Scope official GitHub light/dark styles to code, preserving native app CSS."""
    parts = []
    for theme, file in [('light', 'github.css'), ('dark', 'github-dark.css')]:
        css = re.sub(r'/\*.*?\*/', '', (HIGHLIGHT / file).read_text(), flags=re.S)
        for selectors, rules in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            scoped = ','.join(
                f'.github-{theme}' if selector.strip() == '.hljs'
                else f'.github-{theme} {selector.strip()}'
                for selector in selectors.split(',')
            )
            parts.append(scoped + '{' + rules + '}')
    return ''.join(parts)


def browser_script() -> str:
    """Highlight complete blocks, then split balanced spans without changing source."""
    return (HIGHLIGHT / 'highlight.min.js').read_text() + '\n' + (HIGHLIGHT / 'r.min.js').read_text() + r'''
window.shinyHighlightLines = (source, language = 'python') => {
  const container = document.createElement('span');
  const aliases = {jsx:'javascript', tsx:'typescript', sh:'bash'};
  language = aliases[language] || language;
  container.innerHTML = hljs.highlight(source, {
    language: hljs.getLanguage(language) ? language : 'plaintext', ignoreIllegals: true
  }).value;
  const lines = [document.createElement('span')];
  const walk = (node, classes = []) => {
    if (node.nodeType === Node.TEXT_NODE) {
      node.textContent.split('\n').forEach((part, index) => {
        if (index) lines.push(document.createElement('span'));
        const span = document.createElement('span');
        span.className = classes.join(' ');
        span.textContent = part;
        lines.at(-1).append(span);
      });
    } else {
      for (const child of node.childNodes) walk(child, [...classes, node.className || '']);
    }
  };
  walk(container);
  return lines.map(line => line.innerHTML);
};
void 0;
'''
