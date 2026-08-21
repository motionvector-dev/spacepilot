import unittest
from unittest.mock import patch, MagicMock
from src.cli import cmd_doctor

class TestCliDoctor(unittest.TestCase):
    @patch('src.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_cmd_doctor(self, mock_subprocess_run, mock_probe):
        # Mock device profile
        mock_profile = MagicMock()
        mock_profile.os_type = "macOS"
        mock_profile.architecture = "arm64"
        mock_profile.backend = "metal"
        mock_profile.device_name = "M2 Max"
        mock_profile.vram_usable_gb = 24.0
        mock_profile.vram_total_gb = 32.0
        mock_profile.ram_free_gb = 16.0
        mock_profile.ram_total_gb = 32.0
        mock_probe.return_value = mock_profile

        # Mock subprocess (ffmpeg and aws sts)
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="ffmpeg version 6.0\n"),
            MagicMock(stdout='{"Arn": "arn:aws:iam::123456789012:user/test"}')
        ]

        cfg = {"aws_profile": "default"}
        args = MagicMock()

        # Just test it runs without exceptions
        try:
            cmd_doctor(args, cfg)
        except Exception as e:
            self.fail(f"cmd_doctor raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
