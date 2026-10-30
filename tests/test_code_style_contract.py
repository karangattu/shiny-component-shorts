"""Rendered code keeps its text and uses GitHub syntax colors offline."""
import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.agents/skills/shiny-component-shorts/scripts'))
import record_demo  # noqa: E402

class CodeStyleTest(unittest.TestCase):
    def test_recorder_uses_github_colors_and_bslib_fonts(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width':720, 'height':1280})
            page.set_content('<body style="font-family:serif">App</body>')
            page.evaluate(record_demo.CODE_OVERLAY_JS, {
                'text': 'def answer():\n    return "<value>" # comment',
                'language': 'python', 'title': 'app.py', 'layout': 'bottom',
                'before': '', 'after': '', 'startLine': 1, 'typeMs': 0,
            })
            # Rendering must use the GitHub dark palette, not custom Shiny token colors.
            keyword = page.locator('#__code_overlay__ .hljs-keyword').first
            self.assertTrue(keyword.count(), 'GitHub highlighter must tokenize the code')
            self.assertEqual(keyword.evaluate('(el)=>getComputedStyle(el).color'), 'rgb(255, 123, 114)')
            self.assertIn('Open Sans', page.locator('#__code_overlay__').evaluate('(el)=>getComputedStyle(el).fontFamily'))
            browser.close()

    def test_multiline_languages_preserve_source(self):
        import code_style
        samples = {
            'python': 'def f():\n    """a <tag>\n    more"""\n    return 42\n',
            'r': 'f <- function(x) {\n  # explain\n  x + 2\n}',
            'typescript': 'const text: string = `first\nsecond`;\n// <tag>',
            'html': '<div title="a">hello &amp; bye</div>',
            'css': '.app { color: #007bc2; }',
            'yaml': 'style: editorial\nshots: []',
            'bash': 'printf "%s\\n" "$value"',
        }
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content('<pre class="github-light"></pre><style>'+code_style.stylesheet()+'</style>')
            page.evaluate(code_style.browser_script())
            for language, source in samples.items():
                with self.subTest(language=language):
                    result = page.evaluate('''({source, language}) => {
                      const rows=shinyHighlightLines(source,language);
                      const pre=document.querySelector('pre');
                      pre.innerHTML=rows.join('\\n');
                      return {text:pre.textContent,tokens:pre.querySelectorAll('[class*="hljs-"]').length};
                    }''', {'source':source,'language':language})
                    self.assertEqual(result['text'], source)
                    self.assertGreater(result['tokens'], 0)
            browser.close()

    def test_legacy_code_and_inline_code_share_github_theme(self):
        import code_style
        import stitch_reel
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width':720, 'height':1280})
            page.set_content('<style>'+stitch_reel.PAGE_CSS+code_style.stylesheet()+'</style>')
            source = 'def answer():\n    return 42'
            page.evaluate(stitch_reel.PAGE_JS, {
                'kind':'explainer','orientation':'vertical','accent':'#007BC2',
                'duration':5,'title':'An example','eyebrow':'Test','sentenceStarts':[],
                'scenes':[{'type':'bullets','at':0,'out':None,
                           'points':[{'text':'Call `answer()`','at':0}],
                           'code':stitch_reel.code_lines(source),'codeAt':0}],
            })
            self.assertEqual(page.locator('.codebox .txt').all_text_contents(), source.splitlines())
            self.assertEqual(page.locator('.codebox .hljs-keyword').first.evaluate('(el)=>getComputedStyle(el).color'), 'rgb(255, 123, 114)')
            self.assertTrue(page.locator('.mono.github-dark').count(), 'Inline code must share the GitHub theme')
            browser.close()
