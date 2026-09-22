import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
from spacepilot.cli import cmd_doctor

class TestCliDoctor(unittest.TestCase):
    @patch('spacepilot.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_cmd_doctor_success(self, mock_subprocess_run, mock_probe):
        # A real profile, not a MagicMock: the usable-memory line is computed by
        # the shared helper now, and a mock would let it print anything.
        from spacepilot.device_probe import GIB, DeviceProfile
        mock_probe.return_value = DeviceProfile(
            os_name="macOS", arch="arm64", backend="metal", gpu_name="M2 Max",
            memory_total_bytes=32 * GIB, memory_free_bytes=16 * GIB,
            memory_unified=True,
            memory_limit_bytes=24 * GIB, memory_limit_source="metal",
        )

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
        self.assertIn("OS/Arch  : darwin / arm64", output)
        self.assertIn("Backend  : METAL", output)
        self.assertIn("Device   : M2 Max", output)
        self.assertIn("VRAM     : 24.00 GiB usable / 32.00 GiB total", output)
        self.assertIn("source: metal", output)
        self.assertIn("reserved: 8.00 GiB", output)
        self.assertIn("FFmpeg   : ✅ Installed", output)
        self.assertIn("AWS Auth : ✅ Valid", output)

    @patch('spacepilot.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_cmd_doctor_missing_deps(self, mock_subprocess_run, mock_probe):
        from spacepilot.device_probe import GIB, DeviceProfile
        mock_probe.return_value = DeviceProfile(
            os_name="Linux", arch="x86_64", backend="cuda", gpu_name="RTX 4090",
            memory_total_bytes=64 * GIB, memory_free_bytes=32 * GIB,
            vram_total_bytes=24 * GIB,
        )

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

    @patch('spacepilot.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_doctor_never_prints_system_ram_as_vram(self, mock_subprocess_run, mock_probe):
        """The Lenovo ideapad line: "12.5GB usable / 15.5GB total" was RAM."""
        from spacepilot.device_probe import DeviceProfile
        profile = DeviceProfile(
            os_name="Linux", arch="x86_64", backend="cpu",
            memory_total_bytes=16_231_648 * 1024,
        )
        profile.unknown["vram_total_bytes"] = "no GPU was detected"
        mock_probe.return_value = profile
        mock_subprocess_run.side_effect = Exception("no tools here")

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            cmd_doctor(MagicMock(), {"aws_profile": "default"})
        finally:
            sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        vram_line = next(l for l in output.splitlines() if "VRAM" in l)
        self.assertIn("unknown", vram_line)
        # 15.48 GiB is this machine's RAM. It must appear on the RAM line only.
        self.assertNotIn("15.4", vram_line)
        self.assertNotIn("12.5", vram_line)
        self.assertIn("15.48 GiB total", next(l for l in output.splitlines() if l.strip().startswith("RAM")))
        self.assertIn("Status   : partial", output)
        self.assertIn("[Not measured]", output)

    @patch('spacepilot.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_doctor_reports_a_card_with_no_runtime_as_unreached(self, mock_subprocess_run, mock_probe):
        from spacepilot.device_probe import GIB, DeviceProfile
        profile = DeviceProfile(
            os_name="Linux", arch="x86_64", backend="cpu",
            memory_total_bytes=16_231_648 * 1024, vram_total_bytes=4 * GIB,
            gpu_name="Topaz XT [Radeon R7 M260/M340/M360]",
        )
        mock_probe.return_value = profile
        mock_subprocess_run.side_effect = Exception("no tools here")

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            cmd_doctor(MagicMock(), {"aws_profile": "default"})
        finally:
            sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("4.00 GiB present, 0 GiB usable", output)
        # "can reach this card" was a claim about the hardware. The probe only
        # knows what it looked for and did not find.
        self.assertIn("no compute runtime SpacePilot can use was detected", output)
        self.assertNotIn("can reach this card", output)

    @patch('spacepilot.device_probe.probe_local_device')
    @patch('subprocess.run')
    def test_doctor_names_a_runtime_it_found_but_cannot_route_through(self, mock_subprocess_run, mock_probe):
        """The Lenovo runs Flux over Vulkan and still reads as a dead machine.

        Silence there is the bug: the user has no way to tell "we found nothing"
        from "we found a path we do not support yet".
        """
        from spacepilot.device_probe import GIB, DeviceProfile
        profile = DeviceProfile(
            os_name="Linux", arch="x86_64", backend="cpu",
            memory_total_bytes=16_231_648 * 1024, vram_total_bytes=4 * GIB,
            gpu_name="Topaz XT [Radeon R7 M260/M340/M360]",
            compute_runtime="vulkan",
            compute_runtime_detail="vulkaninfo reports AMD Radeon R7 M360 (RADV ICELAND)",
        )
        mock_probe.return_value = profile
        mock_subprocess_run.side_effect = Exception("no tools here")

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            cmd_doctor(MagicMock(), {"aws_profile": "default"})
        finally:
            sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("vulkan present but unrouted", output)
        self.assertIn("RADV ICELAND", output)

    def test_default_config_sizing(self):
        from spacepilot.cli import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG["instance_type"], "g6e.2xlarge")
        self.assertEqual(DEFAULT_CONFIG["spot_hourly_rate"], 0.75)

    def test_cmd_deploy_refuses(self):
        """The retired AWS deploy path refuses with exit 2 and runs nothing."""
        from unittest.mock import MagicMock, patch as upatch
        from spacepilot.cli import cmd_deploy

        with upatch('spacepilot.cli.run_cmd') as mock_run_cmd:
            rc = cmd_deploy(MagicMock(), {"key_file": "/tmp/test.pem"})
        self.assertEqual(rc, 2)
        mock_run_cmd.assert_not_called()

    def test_cmd_generate_custom_output_arg(self):
        import argparse
        from spacepilot.cli import main
        # Verify parser handles --output, --stg, and --image-noise-scale without error
        parser = argparse.ArgumentParser()
        # Test cli argument parsing logic via sys.argv mock
        with patch('sys.argv', ['spacepilot', 'generate', 'test prompt', '--output', '/tmp/test.mp4', '--stg', '0.8', '--image-noise-scale', '0.03']):
            with patch('spacepilot.cli.cmd_generate') as mock_gen:
                with patch('spacepilot.cli.get_instance_info') as mock_inst:
                    mock_inst.return_value = {"id": "i-123", "ip": "1.2.3.4", "state": "running"}
                    main()
                    self.assertTrue(mock_gen.called)
                    args, _ = mock_gen.call_args
                    self.assertEqual(args[0].output, '/tmp/test.mp4')
                    self.assertEqual(args[0].stg, 0.8)
                    self.assertEqual(args[0].image_noise_scale, 0.03)

if __name__ == '__main__':
    unittest.main()
