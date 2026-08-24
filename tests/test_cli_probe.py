import json
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

from spacepilot.cli import cmd_probe
from spacepilot.device_probe import GIB, DeviceProfile


def _profile():
    return DeviceProfile(
        os_name="macOS", arch="arm64", backend="metal",
        chip="Apple M1 Max", machine_model="MacBookPro18,4",
        memory_total_bytes=32 * GIB, cpu_cores=10, gpu_cores=32,
        memory_unified=True,
    )


class TestCliProbe(unittest.TestCase):
    @patch("spacepilot.pluto.measurements.write_system")
    @patch("spacepilot.device_probe.probe_local_device")
    def test_read_only_prints_id_and_writes_nothing(self, mock_probe, mock_write):
        mock_probe.return_value = _profile()
        out = StringIO(); sys.stdout = out
        try:
            rc = cmd_probe(MagicMock(save=False, json=False), {})
        finally:
            sys.stdout = sys.__stdout__
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("apple-m1-max-32gb", text)
        self.assertIn("not saved", text)
        mock_write.assert_not_called()

    @patch("spacepilot.pluto.measurements.write_system")
    @patch("spacepilot.device_probe.probe_local_device")
    def test_save_writes_the_record(self, mock_probe, mock_write):
        mock_probe.return_value = _profile()
        mock_write.return_value = "/tmp/registry/systems/apple-m1-max-32gb.yaml"
        out = StringIO(); sys.stdout = out
        try:
            cmd_probe(MagicMock(save=True, json=False), {})
        finally:
            sys.stdout = sys.__stdout__
        mock_write.assert_called_once()
        self.assertIn("recorded", out.getvalue())

    @patch("spacepilot.device_probe.probe_local_device")
    def test_json_is_valid(self, mock_probe):
        mock_probe.return_value = _profile()
        out = StringIO(); sys.stdout = out
        try:
            cmd_probe(MagicMock(save=False, json=True), {})
        finally:
            sys.stdout = sys.__stdout__
        text = out.getvalue()
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        self.assertEqual(data["id"], "apple-m1-max-32gb")


if __name__ == "__main__":
    unittest.main()
