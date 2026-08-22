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

    def test_default_config_sizing(self):
        from src.cli import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG["instance_type"], "g6e.2xlarge")
        self.assertEqual(DEFAULT_CONFIG["spot_hourly_rate"], 0.75)

    @patch('src.cli.get_instance_info')
    @patch('src.cli.run_cmd')
    def test_cmd_deploy_token_forwarding(self, mock_run_cmd, mock_inst_info):
        from src.cli import cmd_deploy
        mock_inst_info.return_value = {"id": "i-12345", "ip": "1.2.3.4", "state": "running"}
        
        args = MagicMock()
        cfg = {"key_file": "/tmp/test.pem"}
        
        with patch.dict('os.environ', {'LOCAL_WORKER_TOKEN': 'secret_worker_token', 'HF_TOKEN': 'secret_hf_token'}):
            cmd_deploy(args, cfg)
            
        # Verify run_cmd calls
        self.assertEqual(mock_run_cmd.call_count, 4)
        # Check that stdin_text passed both tokens
        last_call = mock_run_cmd.call_args_list[-1]
        stdin_text = last_call.kwargs.get("stdin_text") or (last_call[1].get("stdin_text") if len(last_call) > 1 else None)
        self.assertIn("LOCAL_WORKER_TOKEN=secret_worker_token", stdin_text)
        self.assertIn("HF_TOKEN=secret_hf_token", stdin_text)

    def test_cmd_generate_custom_output_arg(self):
        import argparse
        from src.cli import main
        # Verify parser handles --output, --stg, and --image-noise-scale without error
        parser = argparse.ArgumentParser()
        # Test cli argument parsing logic via sys.argv mock
        with patch('sys.argv', ['pluto', 'generate', 'test prompt', '--output', '/tmp/test.mp4', '--stg', '0.8', '--image-noise-scale', '0.03']):
            with patch('src.cli.cmd_generate') as mock_gen:
                with patch('src.cli.get_instance_info') as mock_inst:
                    mock_inst.return_value = {"id": "i-123", "ip": "1.2.3.4", "state": "running"}
                    main()
                    self.assertTrue(mock_gen.called)
                    args, _ = mock_gen.call_args
                    self.assertEqual(args[0].output, '/tmp/test.mp4')
                    self.assertEqual(args[0].stg, 0.8)
                    self.assertEqual(args[0].image_noise_scale, 0.03)

if __name__ == '__main__':
    unittest.main()
