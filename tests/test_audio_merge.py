"""Narration must keep its dynamics when a loudness target exceeds headroom."""
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/shiny-component-shorts/scripts'))
import merge_audio
import batch_process
import build_cache

class AudioMergeTest(unittest.TestCase):
    def test_peak_headroom_limits_gain_without_compression(self):
        self.assertAlmostEqual(merge_audio.linear_gain_db({'input_i':'-23.9','input_tp':'-1.3'}), -.2)
        self.assertEqual(merge_audio.linear_gain_db({'input_i':'-20','input_tp':'-12'}),6)
        with self.assertRaises(ValueError):
            merge_audio.linear_gain_db({'input_i':'-inf','input_tp':'-inf'})

    @patch.object(merge_audio, 'require_nonempty')
    @patch.object(merge_audio.subprocess, 'run')
    @patch.object(merge_audio, 'speech_end', return_value=32.6)
    @patch.object(merge_audio, 'probe_duration', side_effect=[32.6,35])
    @patch.object(merge_audio, 'measure_loudness')
    def test_selected_take_is_encoded_without_filtering_or_gain(self, measure, duration, end, run, require):
        merge_audio.merge(Path('v.mp4'),Path('a.wav'),Path('out.mp4'),preserve_audio=True)
        measure.assert_not_called()
        cmd=run.call_args.args[0]
        # No gain or filtering; only the shared lead-in and padding. The take
        # ends on a word here, so there is no silent tail to fade.
        self.assertEqual(cmd[cmd.index('-af')+1], 'adelay=150:all=1,apad')
        self.assertEqual(cmd[cmd.index('-c:v')+1], 'copy')

    def test_only_the_silent_tail_fades_and_narration_starts_at_the_offset(self):
        chain = merge_audio.narration_filters(None, 40.0, 38.5)
        self.assertEqual(chain, 'afade=t=out:st=38.550:d=0.300,adelay=150:all=1,apad')
        normalized = merge_audio.narration_filters(-2.0, 40.0, 40.0)
        self.assertTrue(normalized.startswith('highpass=f=70,volume=-2.000000dB,'))
        self.assertNotIn('afade', normalized)

    def test_music_bed_loops_under_the_voice_and_fades_with_the_video(self):
        chain = merge_audio.bed_filters(-20.0, 42.0)
        self.assertIn('aloop=loop=-1', chain)
        self.assertIn('atrim=0:42.000', chain)
        self.assertIn('afade=t=out:st=40.800', chain)
        with patch.object(merge_audio, 'require_nonempty'), \
             patch.object(merge_audio.subprocess, 'run') as run, \
             patch.object(merge_audio, 'speech_end', return_value=30.0), \
             patch.object(merge_audio, 'probe_duration', side_effect=[30.0, 33.0]), \
             patch.object(merge_audio, 'measure_loudness', return_value={'input_i': '-30', 'input_tp': '-8'}):
            merge_audio.merge(Path('v.mp4'), Path('a.wav'), Path('o.mp4'), preserve_audio=True, bed=Path('bed.wav'))
        cmd = run.call_args.args[0]
        graph = cmd[cmd.index('-filter_complex') + 1]
        self.assertIn('volume=-8.000dB', graph)  # -38 LUFS target from a -30 LUFS bed
        self.assertIn('amix=inputs=2:duration=shortest:normalize=0', graph)

class SelectedTakeSettingsTest(unittest.TestCase):
    def test_removing_processing_settings_invalidates_cached_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source, settings, output = (project / name for name in ('video.mp4', 'tts-settings.json', 'out.mp4'))
            for path in (source, settings, output):
                path.write_text('data')
            build_cache.update_cache(project, 'merge', [source, settings])
            self.assertTrue(build_cache.check_cache(project, 'merge', [source, settings], [output]))
            settings.unlink()
            self.assertFalse(build_cache.check_cache(project, 'merge', [source], [output]))

    def test_preserve_setting_reaches_merge_and_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            settings = project / 'tts-settings.json'
            settings.write_text(json.dumps({'audio_source':'chosen.wav','audio_processing':'preserve'}))
            self.assertIn(settings, batch_process.merge_inputs(project))
            result = batch_process.new_result(project)
            with patch.object(batch_process.subprocess, 'run') as run, \
                 patch.object(batch_process, 'require_nonempty'), \
                 patch.object(batch_process.build_cache, 'update_cache'):
                run.return_value.returncode = 0
                batch_process.merge_project(project, result, force=True)
            self.assertEqual(result['merge'], 'SUCCESS')
            self.assertIn('--preserve-audio', run.call_args.args[0])
            settings.write_text(json.dumps({'audio_processing':'compress'}))
            with self.assertRaisesRegex(ValueError, 'audio_processing'):
                batch_process.load_tts_settings(project)

if __name__ == '__main__':
    unittest.main()
