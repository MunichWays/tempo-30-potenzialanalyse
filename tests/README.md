# Principal assumptions of the analysis

These tests document the decisions that matter to the analysis.

| Topic | Principal assumptions | Tests |
| --- | --- | --- |
| Input | Missing speed is not guessed; conditional speed retains its schedule and permanent-speed context. | [Inputs](test_inputs.py) |
| Nearby sources | Select fast roads and their contributing sources; measure polygon edges; report each identity once. | [Nearby sources](test_nearby_sources.py) |
| Gaps | Require enclosure by slow roads, a connected corridor no longer than 500 m, and a consistent logical street continuation. | [Gap potentials](test_gap_potentials.py) |
| Reasons | Preserve single reasons, combine multiple reasons, and leave unrelated roads unchanged. | [Annotations](test_annotations.py) |

## Gap examples

`test_gap_potentials.py` proceeds from enclosure to the continuation rules that
determine the logical **Straßenführung**:

1. A single enclosed fast road is detected.
2. Multiple connected enclosed roads are detected, including a 500 m corridor.
3. An open end prevents detection, on either side.
4. A disconnected slow anchor does not close a gap.
5. Gaps **longer than 500 m** are rejected, for both single and multiple roads.
6. At a mixed junction, follow the straight continuation rather than a side branch.
7. An all-slow junction can anchor a bend.
8. A sharp slow side turn cannot replace an open straight continuation.
9. A fast loop without slow anchors is not a gap.

The length applies to the complete fast corridor, excluding slow anchors.
The suite does not preserve incidental helper behavior or historical bugs as
requirements. Proximity search radii remain tunable; supplied radii in nearby-source
examples are test parameters, not permanent eligibility criteria.

## View the examples

Import [fixtures/scenarios.geojson](fixtures/scenarios.geojson) into a **Test objects**
layer, and [fixtures/groups.geojson](fixtures/groups.geojson) into a separate
**Test groups** layer below it. Zoom to the objects layer. Toggle the groups layer
to show or hide the topic boundaries. It is the single source of spatial fixtures: 16 synthetic
scenarios offshore in the North Sea. No real roads or facilities are represented.
The tests load this exact file; expected values in assertions remain independent
of the popup text.

Five lightly shaded areas group the examples in reading order: input
interpretation, nearby sources, gap enclosure, gap length, and street continuation. Area boundaries and guide markers
are display-only; the tests select road/source objects by scenario and role.

Select an individual object to see its relevant input tags or parsed fields, road
length, and its expected result. Raw coordinates stay in the GeoJSON geometry. Gap roads also list endpoint connections;
nearby-source examples show the supplied search radius and nearby road/source IDs
with their distances. If none are nearby, only the nearest object is listed. Outputs name the selected IDs or parsed schedule, as appropriate. `null` means absent; an empty list means no matches.
Object details open in a popup beside the clicked object (`popupShape: Default`),
including when the containing map otherwise uses a sidebar. Areas show only their
topic title; guide markers show a brief scenario summary. Test object and guide
popups identify the corresponding test filename.

For example, `conditional_speed — road 902` supplies permanent `maxspeed=50`
and `maxspeed:conditional=30 @ (Mo-Fr 18:00-07:00; Sa, Su, PH)`. Its expected output
retains permanent class `50` and adds conditional speed `30`, days `Mo-Fr`, start
`18:00`, end `07:00`, and special tokens `Sa,Su,PH`. The four speed-input variants
are separate roads in the GeoJSON and are passed directly to the parser by the
tests. Annotation merging is tested separately with a non-spatial table in
[test_annotations.py](test_annotations.py): the input selections and expected
merged annotations are visible together in the test. It has no map fixtures.

Display attributes are stripped before data enters the calculation. When updating
an existing uMap import, remove the old combined fixture layer to avoid duplicate
examples and import the two layers separately. To generate a ready-to-import uMap
file containing both layers, run:

```sh
python tests/fixtures/build_fixture_map.py --output /tmp/test-examples.umap
```
The loader preserves the metric fixture grid when converting from longitude and
latitude so coordinate noise does not alter connected endpoints or measured lengths.

## Run

From the repository root:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

To measure coverage and enforce the 90% minimum:

```sh
python -m pip install -r requirements-dev.txt
python -m coverage run -m unittest discover -s tests -v
python -m coverage report -m
python -m coverage html
```

The coverage report includes production retrieval, calculation, storage, export,
plotting, and uMap configuration code. It excludes test code, the network-driven
`main.py` entry point, the standalone crash conversion script, and two dataclass-only
containers. The HTML report is written to `htmlcov/index.html`.

Run the gap assumptions alone:

```sh
python -m unittest discover -s tests -p 'test_gap_potentials.py' -v
```

Tests run offline. The [workflow](../.github/workflows/tests.yml) runs the
suite on pushes and pull requests using Python 3.11.

When contributing, add the smallest example that explains a new semantic decision.
For a spatial decision, put its geometry and inputs in the shared GeoJSON, inside
the relevant topic area. Use ordinary tables for decisions that do not depend on geometry.
Document the concrete input and expected output in its popup and assert the result
independently in Python. The fixture check guards geometry, complete documentation,
area containment and separation; it does not supply expected calculation results.

Live data services, deployment and rendering are outside this suite. The optional
uMap configuration generator is separate from these examples.
