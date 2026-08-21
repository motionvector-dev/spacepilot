import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
from src.cli import cmd_doctor

class TestCliDoctor(unittest.TestCase):
    @patch('src.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_cmd_doctor_success(self, mock_subprocess_run, mock_probe):
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

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            cmd_doctor(args, cfg)
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        
        # Assertions
        self.assertIn("OS/Arch  : macOS / arm64", output)
        self.assertIn("Backend  : METAL", output)
        self.assertIn("Device   : M2 Max", output)
        self.assertIn("VRAM     : 24.0GB usable / 32.0GB total", output)
        self.assertIn("FFmpeg   : ✅ Installed", output)
        self.assertIn("AWS Auth : ✅ Valid", output)

    @patch('src.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_cmd_doctor_missing_deps(self, mock_subprocess_run, mock_probe):
        mock_profile = MagicMock()
        mock_profile.os_type = "Linux"
        mock_profile.architecture = "x86_64"
        mock_profile.backend = "cuda"
        mock_profile.device_name = "RTX 4090"
        mock_profile.vram_usable_gb = 22.0
        mock_profile.vram_total_gb = 24.0
        mock_profile.ram_free_gb = 32.0
        mock_profile.ram_total_gb = 64.0
        mock_probe.return_value = mock_profile

        # Simulate failures for ffmpeg and aws
        mock_subprocess_run.side_effect = Exception("Command not found")

        cfg = {"aws_profile": "default"}
        args = MagicMock()

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            cmd_doctor(args, cfg)
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn("FFmpeg   : ❌ NOT FOUND", output)
        self.assertIn("AWS Auth : ❌ NOT AUTHENTICATED", output)

if __name__ == '__main__':
    unittest.main()
