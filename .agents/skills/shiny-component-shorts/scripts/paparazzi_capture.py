"""Paparazzi capture with the shared Python action runner and exported-video clock."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path


def clock_marker_seconds(vtt: str) -> float:
    """Read our public VTT marker, including any encoder/startup offset."""
    match = re.search(r'(\d{2}):(\d{2}):(\d{2}\.\d+)\s+-->[^\n]*\nshorts-clock(?:\n|$)', vtt)
    if not match:
        raise ValueError('Paparazzi exported no shorts-clock marker; refusing unverified timing')
    hours, minutes, seconds = map(float, match.groups())
    return hours * 3600 + minutes * 60 + seconds


def check_dependencies() -> None:
    """Fail preflight with an installation hint before starting an app."""
    expression = ('needed <- c("paparazzi", "av", "chromote", "jsonlite"); '
                  'quit(status = if (all(vapply(needed, requireNamespace, logical(1), quietly=TRUE))) 0 else 1)')
    try:
        result = subprocess.run(['Rscript', '-e', expression], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Paparazzi needs Rscript on PATH and an R library with paparazzi and av') from exc
    if result.returncode:
        raise RuntimeError('Paparazzi needs paparazzi and av installed; set R_LIBS_USER to their R library')


class PaparazziCapture:
    """Keep R's capture loop running while Playwright drives its Chromium tab."""

    def __init__(self, artifacts: Path, width: int, height: int) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix='shorts-paparazzi-')
        self.control = Path(self.directory.name)
        self.raw = artifacts / 'paparazzi-raw.mp4'
        config = {'control_dir': str(self.control), 'output': str(self.raw),
                  'width': width, 'height': height, 'timeout': 600}
        (self.control / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        self.log_path = artifacts / 'paparazzi.log'
        self.log = self.log_path.open('w', encoding='utf-8')
        self.proc = subprocess.Popen(
            ['Rscript', str(Path(__file__).with_suffix('.R')), str(self.control / 'config.json')],
            stdout=self.log, stderr=subprocess.STDOUT,
        )
        try:
            self.ready = self.wait('ready', 60)
        except BaseException:
            self.close()
            raise

    def wait(self, name: str, timeout: float) -> dict:
        path = self.control / f'{name}.json'
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return json.loads(path.read_text(encoding='utf-8'))
            if self.proc.poll() is not None:
                raise RuntimeError(f'Paparazzi failed:\n{self.log_path.read_text(encoding="utf-8")[-3000:]}')
            time.sleep(0.02)
        raise RuntimeError(f'Paparazzi timed out waiting for {name}; see {self.log_path}')

    def start(self) -> float:
        (self.control / 'start').touch()
        self.started = self.wait('started', 30)
        if self.started['clock_uncertainty_seconds'] > 0.05:
            raise RuntimeError('Paparazzi clock handshake exceeded 50 ms; record again')
        return time.monotonic() + self.started['epoch'] - time.time()

    def stop(self) -> float:
        (self.control / 'stop').touch()
        self.wait('stopped', 180)
        self.proc.wait(timeout=10)
        return clock_marker_seconds(self.raw.with_suffix('.vtt').read_text(encoding='utf-8'))

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.log.close()
        self.directory.cleanup()


def record(project_dir: Path, app_type: str, run: dict, app_dir: Path, recorder) -> Path:
    """Capture a settled R app and write the same artifacts as the default backend."""
    from playwright.sync_api import sync_playwright

    artifacts = project_dir / 'artifacts'
    artifacts.mkdir(parents=True, exist_ok=True)
    width, height = recorder.viewport_size(run['orientation'])
    actions = run['config']['actions']
    cues = recorder.resolve_cues(actions, project_dir)
    output = artifacts / Path(run['config'].get('video_name', 'demo.webm')).with_suffix('.mp4').name
    app = recorder.start_app_with_retry(app_dir, app_type, run['bind_host'], run['port'],
                                        run['url'], artifacts / 'app.log')
    capture = None
    try:
        capture = PaparazziCapture(artifacts, width, height)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(capture.ready['endpoint'])
            context = browser.contexts[0]
            # Match the target rather than assuming the first Chrome tab belongs to us.
            page = next(page for page in context.pages
                        if context.new_cdp_session(page).send('Target.getTargetInfo')['targetInfo']['targetId']
                        == capture.ready['target'])
            context.add_init_script(recorder.CURSOR_OVERLAY_JS)
            context.add_init_script(recorder.SHINY_CLIENT_ERROR_GUARD_JS)
            context.add_init_script(recorder.SHINY_IDLE_TRACKER_JS)
            context.add_init_script(f'({recorder.LOGO_OVERLAY_JS})({json.dumps(run["logo"])})')
            page.goto(run['url'])
            page.wait_for_load_state('networkidle')
            recorder.rest_cursor(page, width, height)
            recorder.wait_for_shiny_ready(page)
            recorder.assert_no_shiny_client_errors(page)
            recorder.assert_branding_visible(page)
            missing = [s for s in recorder.collect_selectors(actions) if page.locator(s).count() == 0]
            if missing:
                raise RuntimeError('Selectors not found on initial page: ' + ', '.join(missing))
            zero = capture.start()
            recorder.hide_logo_after(page, run['logo']['seconds'] - (time.monotonic() - zero))
            recorder.wait_until(page, zero + recorder.LEAD_SECONDS)
            timeline = recorder.run_actions(page, actions, project_dir, run['orientation'],
                                             clock_zero=zero, cues=cues, video_zero=zero)
            recorder.assert_no_shiny_client_errors(page)
            recorder.assert_branding_visible(page)
            end = next((e['start'] for e in timeline if e['action'] == 'screenshot'), timeline[-1]['end'])
            marker = capture.stop()
            # Disconnect only; the R helper owns the browser and its teardown.
        subprocess.run([
            'ffmpeg', '-loglevel', 'error', '-y', '-i', str(capture.raw),
            '-ss', f'{marker:.3f}', '-t', f'{end:.3f}', '-vf', 'fps=30,format=yuv420p',
            '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-movflags', '+faststart', str(output),
        ], check=True)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError('Paparazzi did not produce a non-empty MP4')
        # Playwright screenshots can reset a CDP-owned page's pixel density.
        # Use the encoded final frame so the review matches the delivered video.
        subprocess.run([
            'ffmpeg', '-loglevel', 'error', '-y', '-sseof', '-0.05', '-i', str(output),
            '-frames:v', '1', '-update', '1', str(artifacts / 'final.png'),
        ], check=True)
        logo = run['logo']
        metadata = {
            'action_timeline': timeline,
            'capture': {'mode': 'paparazzi', 'fps': 30, 'version': capture.ready['version'],
                        'clock': 'Paparazzi public WebVTT marker, continuous capture',
                        'clock_marker_seconds': marker,
                        'clock_uncertainty_seconds': capture.started['clock_uncertainty_seconds']},
            'logo': {'source': run['logo_path'].name, 'width': logo['width'],
                     'top': logo['top'], 'left': logo['left'], 'visible_seconds': logo['seconds']},
            'narration_offset_seconds': recorder.align_narration.NARRATION_OFFSET_SECONDS,
            'orientation': run['orientation'], 'scale_factor': 2,
            'trimmed_preamble_seconds': marker, 'width': width * 2, 'height': height * 2,
            'video': output.name,
        }
        (artifacts / 'recording.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        return output
    finally:
        if capture is not None:
            capture.close()
        recorder.terminate_process(app)
