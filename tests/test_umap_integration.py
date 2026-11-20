"""Exercise the uMap configuration generator with local templates."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from UmapIntegration.build_umap_configuration import _build, main


class UmapConfigurationTests(unittest.TestCase):
    def test_build_rewrites_nested_relative_urls_and_keeps_template(self):
        """Unit under test: UmapIntegration.build_umap_configuration._build;
        update relative remote URLs recursively."""
        document = {"properties": {"name": "Old"}, "layers": [
            {"layers": [{"properties": {"remoteData": {"url": "roads.geojson"}}}]},
            {"properties": {"remoteData": {"url": "https://other.test/fixed.geojson"}}},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template.umap"
            output = Path(directory) / "output.umap"
            template.write_text(json.dumps(document), encoding="utf-8")
            built = _build(output=output, template=template,
                          remote_base="https://example.test/maps", map_name="New")
            self.assertEqual(built["layers"][0]["layers"][0]["properties"]["remoteData"]["url"],
                             "https://example.test/maps/roads.geojson")
            self.assertEqual(built["layers"][1]["properties"]["remoteData"]["url"],
                             "https://other.test/fixed.geojson")
            self.assertEqual(built["properties"]["name"], "New")
            self.assertEqual(json.loads(output.read_text()), built)
            self.assertEqual(json.loads(template.read_text()), document)

    def test_build_rejects_overwriting_template(self):
        """Unit under test: UmapIntegration.build_umap_configuration._build;
        reject the same path for template and output."""
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template.umap"
            template.write_text(json.dumps({"layers": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                _build(output=template, template=template, remote_base="https://example.test/")

    def test_main_accepts_cli_arguments(self):
        """Unit under test: UmapIntegration.build_umap_configuration.main;
        parse arguments and write the requested map."""
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template.umap"
            output = Path(directory) / "output.umap"
            template.write_text(json.dumps({"layers": []}), encoding="utf-8")
            with patch("sys.argv", ["umap", "--template", str(template), "--output",
                                    str(output), "--map-name", "Example"]), \
                    redirect_stdout(StringIO()):
                main()
            self.assertEqual(json.loads(output.read_text())["properties"]["name"], "Example")
