"""Paparazzi must preserve narration cues and the existing recorder contract."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COPIES = [ROOT / folder / 'skills/shiny-component-shorts/scripts'
          for folder in ('.agents', '.claude')]


def load(scripts: Path, name: str) -> Any:
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(f'paparazzi_test_{name}', scripts / f'{name}.py')
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


class PaparazziContractTest(unittest.TestCase):
    def test_cli_offers_paparazzi_capture(self):
        for scripts in COPIES:
            result = subprocess.run([sys.executable, str(scripts / 'record_demo.py'), '--help'],
                                    capture_output=True, text=True, check=True)
            self.assertIn('paparazzi', result.stdout)

    def test_capture_setting_survives_companions_and_rejects_wrong_runtime(self):
        for scripts in COPIES:
            recorder = load(scripts, 'record_demo')
            resolve = getattr(recorder, 'resolve_capture', None)
            self.assertTrue(callable(resolve), 'The recorder needs to resolve actions.yaml capture settings')
            self.assertEqual(resolve(None, {}, 'r'), 'screencast')
            self.assertEqual(resolve(None, {'capture': 'paparazzi'}, 'r'), 'paparazzi')
            self.assertEqual(resolve('playwright', {'capture': 'paparazzi'}, 'python'), 'playwright')
            with self.assertRaisesRegex(ValueError, 'R Shiny'):
                resolve(None, {'capture': 'paparazzi'}, 'python')
            for invalid in ('typo', ['paparazzi'], {}, None, True):
                with self.assertRaisesRegex(ValueError, 'capture'):
                    resolve(None, {'capture': invalid}, 'r')

    def test_companion_keeps_capture_backend_and_flips_only_orientation(self):
        import tempfile
        import yaml
        for scripts in COPIES:
            companion = load(scripts, 'companion')
            with tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                original = {'capture': 'paparazzi', 'orientation': 'vertical',
                            'actions': [{'cue': {'at': 2}}, {'click': '#go'}]}
                (project / 'actions.yaml').write_text(yaml.safe_dump(original))
                target = companion.prepare_companion(project)
                actual = yaml.safe_load((target / 'actions.yaml').read_text())
                self.assertEqual(actual, {**original, 'orientation': 'horizontal'})

    def test_preflight_rejects_r_capture_for_python_before_launching(self):
        import tempfile
        import yaml
        for scripts in COPIES:
            recorder = load(scripts, 'record_demo')
            with tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                actions = project / 'actions.yaml'
                actions.write_text(yaml.safe_dump({'capture': 'paparazzi', 'actions': []}))
                # An invalid runtime must never get as far as starting this app.
                recorder.start_app_with_retry = lambda *args: self.fail('Invalid backend started an app')
                report = recorder.preflight_project(project, 'python', actions, None)
                self.assertTrue(any('R Shiny' in problem for problem in report['problems']))

    def test_exported_clock_marker_accounts_for_initial_video_time(self):
        for scripts in COPIES:
            path = scripts / 'paparazzi_capture.py'
            self.assertTrue(path.is_file(), 'Paparazzi needs an exported-video clock adapter')
            adapter = load(scripts, 'paparazzi_capture')
            vtt = 'WEBVTT\n\n00:00:00.137 --> 00:00:05.200\nshorts-clock\n\n'
            self.assertAlmostEqual(adapter.clock_marker_seconds(vtt), 0.137)
            with self.assertRaisesRegex(ValueError, 'clock'):
                adapter.clock_marker_seconds('WEBVTT\n')


class PaparazziBrowserTest(unittest.TestCase):
    @unittest.skipUnless(__import__('os').environ.get('SHORTS_TEST_PAPARAZZI') == '1',
                         'Set SHORTS_TEST_PAPARAZZI=1 with R, paparazzi and av installed')
    def test_real_capture_matches_actions_to_encoded_frames(self):
        import json
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / 'app.R').write_text('''library(shiny)
ui <- fluidPage(tags$style("body {background:#FFFFFF;padding:25vh 4vw} button {font-size:28px}"),
  tags$script("Shiny.addCustomMessageHandler('color', function(color) {document.body.style.background=color;});"),
  actionButton('go', 'Change color'), textOutput('count'))
server <- function(input, output, session) {
  output$count <- renderText(input$go)
  observeEvent(input$go, {session$sendCustomMessage('color', if(input$go %% 2) '#007BC2' else '#FFFFFF')})
}
shinyApp(ui, server)
''')
            actions = {'capture': 'paparazzi', 'actions': [
                {'cue': {'at': 1.5}}, {'click': '#go'},
                {'cue': {'at': 2.5}}, {'click': '#go'},
                {'cue': {'at': 3.5}}, {'click': '#go'},
                {'wait': 1000}, {'screenshot': {'path': 'artifacts/final.png'}}]}
            (project / 'actions.yaml').write_text(yaml.safe_dump(actions))
            result = subprocess.run([sys.executable, str(COPIES[0] / 'record_demo.py'),
                                     '--project-dir', str(project), '--app-type', 'r'],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            meta = json.loads((project / 'artifacts/recording.json').read_text())
            self.assertEqual(meta['capture']['mode'], 'paparazzi')
            self.assertLess(meta['capture']['clock_uncertainty_seconds'], 0.05)
            clicks = [entry for entry in meta['action_timeline'] if entry['action'] == 'click']
            for entry, target in zip(clicks, (1.65, 2.65, 3.65)):
                self.assertAlmostEqual(entry['reaction'], target, delta=0.15)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                                     str(project / 'artifacts/demo.mp4')], capture_output=True,
                                    text=True, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            self.assertEqual((stream['width'], stream['height']), (1440, 2560))
            still = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                                     str(project / 'artifacts/final.png')], capture_output=True,
                                    text=True, check=True)
            final_frame = json.loads(still.stdout)['streams'][0]
            self.assertEqual((final_frame['width'], final_frame['height']), (1440, 2560))
            # Decode pixels from the actual MP4, independently of the action log.
            for stamp, expected in ((1.0, (255, 255, 255)), (2.1, (0, 123, 194)),
                                    (3.1, (255, 255, 255)), (4.1, (0, 123, 194))):
                sample = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(stamp),
                                         '-i', str(project / 'artifacts/demo.mp4'),
                                         '-vf', 'crop=2:2:10:1200,scale=1:1', '-frames:v', '1',
                                         '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                        capture_output=True, check=True).stdout
                self.assertEqual(len(sample), 3)
                for actual, want in zip(sample, expected):
                    self.assertAlmostEqual(actual, want, delta=6)


if __name__ == '__main__':
    unittest.main()
