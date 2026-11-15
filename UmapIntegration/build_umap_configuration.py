"""Generate a uMap configuration from a template.

The template defines the layers, grouping, colors, styles, popups and permissions.
Remote feature layers are set using the given base URL.

An optional map name overrides the template title. The generated map
is written separately without modifying the template.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit


DEFAULT_REMOTE_BASE = "https://www.munichways.de/App/tempo30_geojson/latest/"
DEFAULT_TEMPLATE = Path(__file__).with_name("template.umap")


def _build(*, output, template, remote_base, map_name=None):
    """Update deployment settings while preserving all template layer definitions."""
    template, output = Path(template), Path(output)
    if template.resolve() == output.resolve():
        raise ValueError("Output must not overwrite the template")
    url = urlsplit(remote_base)
    document = json.loads(template.read_text(encoding="utf-8"))
    def _update_layers(layers):
        for layer in layers:
            remote = layer.get("properties", {}).get("remoteData", {})
            source = remote.get("url")
            if source and not urlsplit(source).scheme and not urlsplit(source).netloc:
                remote["url"] = urljoin(f"{remote_base.rstrip('/')}/", source)
            _update_layers(layer.get("layers", []))

    _update_layers(document.get("layers", []))
    if map_name is not None:
        document.setdefault("properties", {})["name"] = map_name
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE,
                        help="An exported uMap configuration; defaults to the shipped generic template.")
    parser.add_argument("--output", type=Path, default="tempo30potenziale.umap")
    parser.add_argument("--remote-base", default=DEFAULT_REMOTE_BASE)
    parser.add_argument("--map-name")
    args = parser.parse_args()
    try:
        _build(**vars(args))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Written {args.output}")


if __name__ == "__main__":
    main()
