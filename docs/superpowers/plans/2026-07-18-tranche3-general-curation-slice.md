# Tranche 3 General-Lane Curation Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce forty valid general-lane candidates and complete the first ten-example submitted, independently reviewed, exported, and loaded curation slice.

**Architecture:** Candidate inputs remain public and version-controlled, while annotated answers and review ledgers remain local and gitignored until an intentional immutable release. Export is hardened to require seed re-joining and full `GoldExample` validation. A small review-ledger schema and status utility distinguish candidate, submitted, and independently approved counts before any load is allowed.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Click, Argilla v2, JSONL, PostgreSQL 17, Terraform, GCE e2-standard-2, SSH local forwarding.

## Global Constraints

- Follow red-green-refactor for every Python behavior change.
- Candidate seeds do not count as submitted, reviewed, or released examples.
- Annotated answers and review ledgers are private and remain gitignored before `v0.1` release.
- The first accepted slice contains exactly ten submitted examples, including at least two rubric examples.
- Every exported example requires a matching seed, a non-empty expected answer/rubric, and a real Argilla update timestamp.
- Every exported example requires one independent review decision from a reviewer other than the annotator.
- Load the slice into the test database before the development database.
- Export local artifacts before destroying Argilla; destroy the annotation VM and verify final GCP inventory.
- Do not begin specialist-judge selection, kappa measurement, or bias stress testing in this tranche.

---

### Task 1: Add a real shared QA template and forty candidates

**Files:**
- Create: `templates/qa.j2`
- Create: `tests/shared/goldsets/test_templates.py`
- Modify: `gold_sets/general/seed.jsonl`

**Interfaces:**
- Consumes: `shared.goldsets.render.render_prompt` and the existing default template root in `argilla_push.py`.
- Produces: a renderable `qa` template and exactly 40 unique `SeedExample` rows in the general lane.

- [ ] **Step 1: Write the failing template test**

Create `tests/shared/goldsets/test_templates.py`:

```python
"""Tests for repository-level gold-set prompt templates."""
from __future__ import annotations

from pathlib import Path

from shared.goldsets.render import render_prompt


def test_qa_template_renders_question() -> None:
    root = Path(__file__).resolve().parents[3] / "templates"
    rendered = render_prompt(root, "qa.j2", {"question": "What is 2 + 2?"})
    assert rendered == "What is 2 + 2?\n"
```

- [ ] **Step 2: Run the template test to verify RED**

```bash
uv run pytest tests/shared/goldsets/test_templates.py -v
```

Expected: failure because `templates/qa.j2` does not exist.

- [ ] **Step 3: Create the minimal template**

Create `templates/qa.j2`:

```jinja2
{{ question }}
```

- [ ] **Step 4: Run the template test to verify GREEN**

```bash
uv run pytest tests/shared/goldsets/test_templates.py -v
```

Expected: one test passes.

- [ ] **Step 5: Replace the two-row seed with the exact forty-candidate set**

Every line uses these fixed fields unless the question list below supplies a different tag:

```json
{"lane":"general","source":"handcrafted public candidate","annotator":"huiliang","annotated_at":"2026-07-18","prompt_template":"qa.j2","provenance_tag":"public","never_to_third_party":false,"tags":[],"contamination_risk":"none"}
```

Write one JSON object per line with the listed `example_id` and `inputs.question`. Preserve no expected answer in this seed file.

| ID | Question | Tags |
|---|---|---|
| `ex_general_0001` | What is the capital of France? | `smoke` |
| `ex_general_0002` | If a train travels 120 km in 2 hours, what is its average speed in km/h? | `smoke` |
| `ex_general_0003` | How many days are in a leap year? | none |
| `ex_general_0004` | What number comes next in the sequence 2, 4, 8, 16? | none |
| `ex_general_0005` | What is the probability of getting heads on one fair coin toss? | none |
| `ex_general_0006` | What is the largest prime number less than 10? | none |
| `ex_general_0007` | At standard atmospheric pressure, at what temperature in degrees Celsius does pure water boil? | none |
| `ex_general_0008` | Who wrote the novel 1984? | none |
| `ex_general_0009` | Explain in two sentences why Earth has seasons. | `hard` |
| `ex_general_0010` | Explain the difference between correlation and causation and give one short example. | `hard` |
| `ex_general_0011` | What is 15 percent of 200? | none |
| `ex_general_0012` | What is the area of a rectangle that is 8 metres long and 5 metres wide? | none |
| `ex_general_0013` | What is the arithmetic mean of 3, 5, and 7? | none |
| `ex_general_0014` | Give one concise synonym for the word "brief". | none |
| `ex_general_0015` | All whales are mammals, and all mammals are warm-blooded. Are whales warm-blooded? | none |
| `ex_general_0016` | Put these values in ascending order: 0.5, two-thirds, and 75 percent. | none |
| `ex_general_0017` | What is the decimal value of the binary number 1010? | none |
| `ex_general_0018` | What is the principal square root of 144? | none |
| `ex_general_0019` | A car travels 150 km in 3 hours. What is its average speed in km/h? | none |
| `ex_general_0020` | What is Singapore's standard UTC offset? | none |
| `ex_general_0021` | What is the official currency of Japan? | none |
| `ex_general_0022` | What is the largest ocean on Earth? | none |
| `ex_general_0023` | What is the name of the process in which water vapour becomes liquid water? | none |
| `ex_general_0024` | Correct the grammar in this sentence: "She don't like coffee." | none |
| `ex_general_0025` | If today is Monday, what day of the week will it be 10 days from today? | none |
| `ex_general_0026` | How many days are in 3 weeks and 4 days? | none |
| `ex_general_0027` | What is three-quarters of 80? | none |
| `ex_general_0028` | What is the smallest integer greater than 50 that is divisible by both 3 and 5? | none |
| `ex_general_0029` | What number is represented by the Roman numeral XLIV? | none |
| `ex_general_0030` | What is the SI unit of force? | none |
| `ex_general_0031` | What is Earth's natural satellite called? | none |
| `ex_general_0032` | Which gas do plants absorb from the atmosphere during photosynthesis? | none |
| `ex_general_0033` | What is the largest continent by land area? | none |
| `ex_general_0034` | Solve for x: x + 7 = 19. | none |
| `ex_general_0035` | What is the sum of the interior angles of a triangle in degrees? | none |
| `ex_general_0036` | Are the words "listen" and "silent" anagrams of each other? | none |
| `ex_general_0037` | If it is raining and you stand outside without cover, what is the most likely immediate effect on your clothes? | none |
| `ex_general_0038` | What is 2 raised to the fifth power? | none |
| `ex_general_0039` | What is the perimeter of a square with side length 9 cm? | none |
| `ex_general_0040` | In which century did the year 1905 occur? | none |

For rows tagged `smoke` or `hard`, set `tags` to a one-element JSON list. All other rows use `tags: []`.

- [ ] **Step 6: Validate count, IDs, schema, and rendering**

Run:

```bash
uv run python -m shared.goldsets.cli validate-seed gold_sets/general/seed.jsonl
uv run python -c "import json; from pathlib import Path; rows=[json.loads(x) for x in Path('gold_sets/general/seed.jsonl').read_text().splitlines() if x.strip()]; assert len(rows)==40; assert len({r['example_id'] for r in rows})==40; print('40 unique candidates')"
uv run pytest tests/shared/goldsets/test_templates.py tests/shared/goldsets/test_validate_seed.py -q
```

Expected: validation succeeds, the count command prints `40 unique candidates`, and all selected tests pass.

- [ ] **Step 7: Commit candidate inputs and template**

```bash
git add templates/qa.j2 tests/shared/goldsets/test_templates.py gold_sets/general/seed.jsonl
git commit -m "feat: add forty general-lane curation candidates"
```

---

### Task 2: Require release-quality export records

**Files:**
- Modify: `shared/goldsets/schema.py`
- Modify: `shared/goldsets/argilla_export.py`
- Modify: `shared/goldsets/cli.py`
- Modify: `tests/shared/goldsets/test_schema.py`
- Modify: `tests/shared/goldsets/test_argilla_export.py`

**Interfaces:**
- Consumes: submitted Argilla responses and a required matching seed file.
- Produces: `GoldExample`-validated JSONL only; missing seed, missing timestamp, blank exact/set answer, empty set, and blank rubric are hard failures.

- [ ] **Step 1: Write failing `Expected` quality tests**

Append to `tests/shared/goldsets/test_schema.py`:

```python
def test_exact_rejects_blank_value() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        Expected(type="exact", value="   ")


def test_set_rejects_empty_list() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        Expected(type="set", value=[])


def test_rubric_rejects_blank_text() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        Expected(type="rubric", rubric="   ")
```

- [ ] **Step 2: Write failing export-quality tests**

Append to `tests/shared/goldsets/test_argilla_export.py`:

```python
def test_export_requires_seed_file(tmp_path):
    from shared.goldsets.argilla_export import export_lane

    with pytest.raises(ValueError, match="seed file is required"):
        export_lane("general", tmp_path / "out.jsonl", "http://localhost", "key")


def test_export_rejects_record_missing_from_seed(tmp_path):
    from shared.goldsets.argilla_export import export_lane

    seed_file = tmp_path / "seed.jsonl"
    seed_file.write_text(json.dumps({
        "example_id": "ex_general_0001",
        "lane": "general",
        "annotator": "huiliang",
        "annotated_at": "2026-07-18",
        "prompt_template": "qa.j2",
        "inputs": {"question": "Q"},
    }) + "\n")
    record = _make_record("ex_general_9999")

    with patch("shared.goldsets.argilla_export.rg.Argilla",
               return_value=_mock_argilla([record])):
        with pytest.raises(ValueError, match="no matching seed"):
            export_lane(
                "general", tmp_path / "out.jsonl", "http://localhost", "key",
                seed_path=seed_file,
            )


def test_export_rejects_missing_update_timestamp(tmp_path):
    from shared.goldsets.argilla_export import export_lane

    seed_file = tmp_path / "seed.jsonl"
    seed_file.write_text(json.dumps({
        "example_id": "ex_general_0001",
        "lane": "general",
        "annotator": "huiliang",
        "annotated_at": "2026-07-18",
        "prompt_template": "qa.j2",
        "inputs": {"question": "Q"},
    }) + "\n")
    record = _make_record("ex_general_0001")
    record.updated_at = None

    with patch("shared.goldsets.argilla_export.rg.Argilla",
               return_value=_mock_argilla([record])):
        with pytest.raises(ValueError, match="updated_at"):
            export_lane(
                "general", tmp_path / "out.jsonl", "http://localhost", "key",
                seed_path=seed_file,
            )
```

Re-add `import pytest` to this test file because the new tests use it.

- [ ] **Step 3: Run the new tests to verify RED**

```bash
uv run pytest tests/shared/goldsets/test_schema.py tests/shared/goldsets/test_argilla_export.py -v
```

Expected: the six new tests fail against permissive schema/export behavior.

- [ ] **Step 4: Tighten `Expected` validation**

Replace `_check_type_fields` in `shared/goldsets/schema.py` with:

```python
    @model_validator(mode="after")
    def _check_type_fields(self) -> "Expected":
        if self.type == "exact":
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError("expected.value must be a non-empty string for type='exact'")
            self.value = self.value.strip()
        elif self.type == "set":
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("expected.value must be a non-empty list for type='set'")
            if not all(isinstance(item, str) and item.strip() for item in self.value):
                raise ValueError("expected.value set items must be non-empty strings")
            self.value = [item.strip() for item in self.value]
        elif self.type == "rubric":
            if not isinstance(self.rubric, str) or not self.rubric.strip():
                raise ValueError("expected.rubric must be non-empty for type='rubric'")
            self.rubric = self.rubric.strip()
            if self.reference is not None:
                self.reference = self.reference.strip() or None
        return self
```

- [ ] **Step 5: Enforce seed matching and full validation during export**

In `shared/goldsets/argilla_export.py`, import both models:

```python
from shared.goldsets.schema import GoldExample, SeedExample
```

At the start of `export_lane`, replace optional seed loading with:

```python
    if seed_path is None or not seed_path.is_file():
        raise ValueError("seed file is required for release-quality export")

    seed_lookup: dict[str, SeedExample] = {}
    with seed_path.open() as seed_file:
        for line in seed_file:
            if line.strip():
                seed = SeedExample.model_validate(json.loads(line))
                seed_lookup[seed.example_id] = seed
```

Inside the submitted-record loop, before building `row`, add:

```python
        seed = seed_lookup.get(record.id)
        if seed is None:
            raise ValueError(f"record {record.id}: no matching seed")
        if record.updated_at is None:
            raise ValueError(f"record {record.id}: updated_at is required")
```

Build the row only from the matched seed and timestamp:

```python
        row = {
            "example_id": record.id,
            "lane": lane,
            "annotator": "argilla",
            "annotated_at": str(record.updated_at.date()),
            "prompt_template": seed.prompt_template,
            "inputs": dict(seed.inputs),
            "expected": expected,
            "source": seed.source,
            "provenance_tag": seed.provenance_tag,
            "never_to_third_party": never_ttp == "true",
            "tags": answers.get("tags") or [],
            "contamination_risk": answers.get("contamination_risk", "none"),
        }
        exported.append(GoldExample.model_validate(row).model_dump(mode="json"))
```

Delete the old fallback row construction and the comment that says not to validate `GoldExample`.

- [ ] **Step 6: Make the CLI require the resolved seed path**

In `cmd_export`, after resolving the default seed, add:

```python
    if seed_file is None or not seed_file.is_file():
        raise click.ClickException("seed file is required for export")
```

Keep passing `seed_path=seed_file` to `export_lane`.

- [ ] **Step 7: Run tests to verify GREEN**

```bash
uv run pytest tests/shared/goldsets/test_schema.py tests/shared/goldsets/test_argilla_export.py -v
uv run ruff check shared/goldsets/schema.py shared/goldsets/argilla_export.py shared/goldsets/cli.py tests/shared/goldsets/test_schema.py tests/shared/goldsets/test_argilla_export.py
```

Expected: all tests pass and Ruff is clean.

- [ ] **Step 8: Commit export hardening**

```bash
git add shared/goldsets/schema.py shared/goldsets/argilla_export.py shared/goldsets/cli.py \
  tests/shared/goldsets/test_schema.py tests/shared/goldsets/test_argilla_export.py
git commit -m "fix: enforce release-quality gold-set exports"
```

---

### Task 3: Add an independent review ledger and status gate

**Files:**
- Create: `shared/goldsets/review.py`
- Create: `tests/shared/goldsets/test_review.py`
- Modify: `shared/goldsets/schema.py`
- Modify: `shared/goldsets/cli.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `ReviewRecord(example_id, reviewer, reviewed_at, decision, notes)`.
- Produces: `validate_review(annotated_path: Path, review_path: Path, *, annotator: str) -> list[str]`.
- Produces: `curation_status(seed_path: Path, annotated_path: Path, review_path: Path) -> dict[str, int]`.
- Produces CLI commands `validate-review` and `status`.

- [ ] **Step 1: Write failing review tests**

Create `tests/shared/goldsets/test_review.py`:

```python
"""Tests for independent review validation and curation counts."""
from __future__ import annotations

import json
from pathlib import Path

from shared.goldsets.review import curation_status, validate_review


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def _annotated(example_id: str) -> dict:
    return {"example_id": example_id}


def _review(example_id: str, reviewer: str = "reviewer") -> dict:
    return {
        "example_id": example_id,
        "reviewer": reviewer,
        "reviewed_at": "2026-07-18",
        "decision": "approved",
        "notes": "Checked against an independent calculation or source.",
    }


def test_validate_review_accepts_one_independent_decision_per_example(tmp_path: Path) -> None:
    annotated = tmp_path / "annotated.jsonl"
    reviews = tmp_path / "review.jsonl"
    _write(annotated, [_annotated("ex_general_0001")])
    _write(reviews, [_review("ex_general_0001")])
    assert validate_review(annotated, reviews, annotator="argilla") == []


def test_validate_review_rejects_missing_decision(tmp_path: Path) -> None:
    annotated = tmp_path / "annotated.jsonl"
    reviews = tmp_path / "review.jsonl"
    _write(annotated, [_annotated("ex_general_0001"), _annotated("ex_general_0002")])
    _write(reviews, [_review("ex_general_0001")])
    errors = validate_review(annotated, reviews, annotator="argilla")
    assert errors == ["missing review: ex_general_0002"]


def test_validate_review_rejects_same_person(tmp_path: Path) -> None:
    annotated = tmp_path / "annotated.jsonl"
    reviews = tmp_path / "review.jsonl"
    _write(annotated, [_annotated("ex_general_0001")])
    _write(reviews, [_review("ex_general_0001", reviewer="argilla")])
    errors = validate_review(annotated, reviews, annotator="argilla")
    assert errors == ["reviewer must differ from annotator: ex_general_0001"]


def test_validate_review_rejects_duplicate_review(tmp_path: Path) -> None:
    annotated = tmp_path / "annotated.jsonl"
    reviews = tmp_path / "review.jsonl"
    _write(annotated, [_annotated("ex_general_0001")])
    _write(reviews, [_review("ex_general_0001"), _review("ex_general_0001", "reviewer2")])
    errors = validate_review(annotated, reviews, annotator="argilla")
    assert errors == ["duplicate review: ex_general_0001"]


def test_curation_status_counts_each_state(tmp_path: Path) -> None:
    seed = tmp_path / "seed.jsonl"
    annotated = tmp_path / "annotated.jsonl"
    reviews = tmp_path / "review.jsonl"
    _write(seed, [{"example_id": "ex_general_0001"}, {"example_id": "ex_general_0002"}])
    _write(annotated, [_annotated("ex_general_0001")])
    _write(reviews, [_review("ex_general_0001")])
    assert curation_status(seed, annotated, reviews) == {
        "candidates": 2,
        "submitted": 1,
        "approved": 1,
        "rejected": 0,
    }
```

- [ ] **Step 2: Run review tests to verify RED**

```bash
uv run pytest tests/shared/goldsets/test_review.py -v
```

Expected: import failure because `shared.goldsets.review` does not exist.

- [ ] **Step 3: Add `ReviewRecord` to the schema**

Append to `shared/goldsets/schema.py`:

```python
class ReviewRecord(BaseModel):
    """Independent human review decision for one annotated example."""

    example_id: str
    reviewer: str
    reviewed_at: date
    decision: Literal["approved", "rejected"]
    notes: str

    @field_validator("example_id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not EXAMPLE_ID_RE.match(value):
            raise ValueError(f"example_id {value!r} must match {EXAMPLE_ID_RE.pattern}")
        return value

    @field_validator("reviewer", "notes")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value.strip()
```

- [ ] **Step 4: Implement review validation and status**

Create `shared/goldsets/review.py`:

```python
"""Independent-review validation and curation state counts."""
from __future__ import annotations

import json
from pathlib import Path

from shared.goldsets.schema import ReviewRecord


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_review(
    annotated_path: Path,
    review_path: Path,
    *,
    annotator: str,
) -> list[str]:
    annotated_ids = {row["example_id"] for row in _rows(annotated_path)}
    review_rows = [ReviewRecord.model_validate(row) for row in _rows(review_path)]
    errors: list[str] = []
    seen: set[str] = set()

    for review in review_rows:
        if review.example_id in seen:
            errors.append(f"duplicate review: {review.example_id}")
            continue
        seen.add(review.example_id)
        if review.example_id not in annotated_ids:
            errors.append(f"review for unknown example: {review.example_id}")
        if review.reviewer == annotator:
            errors.append(f"reviewer must differ from annotator: {review.example_id}")

    for example_id in sorted(annotated_ids - seen):
        errors.append(f"missing review: {example_id}")
    return errors


def curation_status(
    seed_path: Path,
    annotated_path: Path,
    review_path: Path,
) -> dict[str, int]:
    seed_rows = _rows(seed_path)
    annotated_rows = _rows(annotated_path)
    review_rows = [ReviewRecord.model_validate(row) for row in _rows(review_path)]
    return {
        "candidates": len(seed_rows),
        "submitted": len(annotated_rows),
        "approved": sum(row.decision == "approved" for row in review_rows),
        "rejected": sum(row.decision == "rejected" for row in review_rows),
    }
```

- [ ] **Step 5: Add CLI commands**

Import the functions in `shared/goldsets/cli.py`:

```python
from shared.goldsets.review import curation_status, validate_review
```

Add:

```python
@cli.command("validate-review")
@click.option("--annotated", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--reviews", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--annotator", required=True)
def cmd_validate_review(annotated: Path, reviews: Path, annotator: str) -> None:
    """Require one independent review decision per annotated example."""
    errors = validate_review(annotated, reviews, annotator=annotator)
    if errors:
        for error in errors:
            click.echo(f"ERROR: {error}", err=True)
        raise click.ClickException(f"{len(errors)} review validation error(s)")
    click.echo("OK: every annotated example has one independent review")


@cli.command("status")
@click.option("--seed", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--annotated", required=True, type=click.Path(path_type=Path))
@click.option("--reviews", required=True, type=click.Path(path_type=Path))
def cmd_status(seed: Path, annotated: Path, reviews: Path) -> None:
    """Print separate candidate, submitted, approved, and rejected counts."""
    counts = curation_status(seed, annotated, reviews)
    click.echo(" ".join(f"{key}={value}" for key, value in counts.items()))
```

- [ ] **Step 6: Ignore pre-release private review ledgers**

Add to `.gitignore` immediately after `*/annotated.jsonl`:

```gitignore
*/review.jsonl
```

- [ ] **Step 7: Run review tests to verify GREEN**

```bash
uv run pytest tests/shared/goldsets/test_review.py tests/shared/goldsets/test_schema.py -v
uv run ruff check shared/goldsets/schema.py shared/goldsets/review.py shared/goldsets/cli.py tests/shared/goldsets/test_review.py
```

Expected: all tests pass and Ruff is clean.

- [ ] **Step 8: Commit the review gate**

```bash
git add shared/goldsets/schema.py shared/goldsets/review.py shared/goldsets/cli.py \
  tests/shared/goldsets/test_review.py .gitignore
git commit -m "feat: add independent gold-set review gate"
```

---

### Task 4: Create the curation-slice experiment record

**Files:**
- Create: `experiments/0003-eval-general-curation-slice/README.md`
- Modify: `EXPERIMENTS.md`

**Interfaces:**
- Produces experiment ID `0003-eval-general-curation-slice`.
- Records candidate, submitted, approved, rubric, rejected, and loaded counts separately.

- [ ] **Step 1: Create the experiment README**

Create a README with these exact headings:

```markdown
# 0003 — General-lane curation slice

**Area:** eval · **Status:** running · **Started:** 2026-07-18

## Hypothesis

The seed → Argilla → submitted export → independent review → test load → development load workflow can produce ten release-quality general examples, including at least two rubric examples, without exposing the private annotated data or leaving GCP resources running.

## Acceptance criteria

- candidates: 40
- submitted: 10
- approved: 10
- rejected: recorded separately
- rubric examples: at least 2
- review validator: clean
- test load: 10
- development load: 10 as `general-slice-v0.0`
- final GCP inventory: no resources created by this experiment

## Setup

Argilla runs on the disposable `infra/gcp/annotation` workspace and is accessed only at `http://127.0.0.1:6900` through the SSH tunnel. Candidate inputs are committed in `gold_sets/general/seed.jsonl`; `annotated.jsonl` and `review.jsonl` remain local and gitignored.

## Method

1. Validate and push forty candidates.
2. Submit annotations for examples 0001-0010, using rubric type for 0009 and 0010.
3. Export the ten submitted records.
4. Have a second person independently approve or reject every exported record.
5. Validate the review ledger, test-load, then development-load.
6. Destroy Argilla and verify empty GCP inventory.

## Results

Status: not yet run.

## Calibration entry decision

Blocked until this slice contains ten approved records and at least two approved rubric records. This slice alone does not satisfy the 100-200-example human calibration requirement.
```

- [ ] **Step 2: Register the running experiment**

Add to `EXPERIMENTS.md`:

```markdown
| 0003 | eval | general-curation-slice | running | 2026-07-18 | 40 candidates planned; awaiting 10 submitted and independently reviewed examples |
```

- [ ] **Step 3: Commit the experiment scaffold**

```bash
git add experiments/0003-eval-general-curation-slice/README.md EXPERIMENTS.md
git commit -m "docs: register general-lane curation slice"
```

---

### Task 5: Run the ten-example Argilla session and destroy it

**Files:**
- Runtime-only environment: Terraform variables exported in the annotation shell session
- Runtime-only, gitignored: `gold_sets/general/annotated.jsonl`
- Runtime-only, gitignored: `gold_sets/general/review.jsonl`
- Modify after evidence: `experiments/0003-eval-general-curation-slice/README.md`
- Modify after evidence: `EXPERIMENTS.md`

**Interfaces:**
- Consumes: forty candidates, private Argilla tunnel, hardened exporter, and independent review gate.
- Produces: immutable development/test version `general-slice-v0.0` with exactly ten approved examples.

- [ ] **Step 1: Start one controlled annotation shell and export runtime variables**

Start an interactive shell that remains open through the destroy step, then run:

```bash
export TF_VAR_project_id=adept-prod-497323
export TF_VAR_zone=asia-southeast1-b
export TF_VAR_argilla_username=owner
export TF_VAR_argilla_password="$(openssl rand -base64 24)"
test -n "$TF_VAR_argilla_password"
```

Expected: `test` returns exit code 0. Keep this shell open so both `terraform apply` and
`terraform destroy` receive the same runtime-generated value. The secret is never printed,
written to disk, or committed.

- [ ] **Step 2: Validate the seed and empty pre-run inventory**

```bash
uv run python -m shared.goldsets.cli validate-seed gold_sets/general/seed.jsonl
gcloud compute instances list --project adept-prod-497323
gcloud compute disks list --project adept-prod-497323
gcloud compute addresses list --project adept-prod-497323
gcloud storage buckets list --project adept-prod-497323
```

Expected: seed validation succeeds and inventory contains no recovery-created resources.

- [ ] **Step 3: Apply Argilla**

```bash
terraform -chdir=infra/gcp/annotation apply -auto-approve -input=false
```

Expected: one `argilla-annotation-server` instance. On apply failure, destroy immediately and verify inventory before stopping.

- [ ] **Step 4: Start and verify the private tunnel**

In a dedicated terminal/session:

```bash
make -C infra/gcp/annotation tunnel
```

In the main terminal:

```bash
make -C infra/gcp/annotation health
```

Expected: `Ready: http://127.0.0.1:6900`.

- [ ] **Step 5: Push all candidates idempotently**

```bash
uv run python -m shared.goldsets.cli push \
  --lane general \
  --argilla-url http://127.0.0.1:6900 \
  --api-key owner.apikey \
  --seed-file gold_sets/general/seed.jsonl
```

Expected first run: `Pushed 40 new records to lane-general`. A repeat prints 0.

- [ ] **Step 6: Pause for human annotation and submission**

Open `http://127.0.0.1:6900` and submit exactly examples `ex_general_0001` through `ex_general_0010`.

Required annotation choices:

- 0001-0008: choose `exact` or `set`, enter the independently checked expected answer, set privacy and contamination fields.
- 0009-0010: choose `rubric`, enter a complete scoring rubric and a reference answer.
- Do not submit 0011-0040 in this slice.

This is a blocking human-quality step. Do not synthesize a completed status from pushed candidates.

- [ ] **Step 7: Export exactly the submitted slice before teardown**

```bash
uv run python -m shared.goldsets.cli export \
  --lane general \
  --out gold_sets/general/annotated.jsonl \
  --argilla-url http://127.0.0.1:6900 \
  --api-key owner.apikey \
  --seed-file gold_sets/general/seed.jsonl
uv run python -c "import json; from pathlib import Path; rows=[json.loads(x) for x in Path('gold_sets/general/annotated.jsonl').read_text().splitlines() if x.strip()]; assert len(rows)==10; assert sum(r['expected']['type']=='rubric' for r in rows)>=2; print('submitted=10 rubric>=2')"
```

Expected: exporter reports 10 and the count check passes. If it does not, keep the VM only while correcting/exporting, then continue to teardown.

- [ ] **Step 8: Perform and record independent review**

A person other than the Argilla annotator checks each exported answer/rubric against an
independent calculation or authoritative source and writes one JSON line per exported ID to
`gold_sets/general/review.jsonl`. Every line must contain the exact exported `example_id`, the
reviewer's real identity, the actual review date, `decision` set to `approved` or `rejected`,
and a non-empty `notes` string describing the independent calculation or source used. Review
all ten exported IDs; fabricated identities or generic notes do not satisfy the gate.

- [ ] **Step 9: Validate review and counts**

```bash
uv run python -m shared.goldsets.cli validate-review \
  --annotated gold_sets/general/annotated.jsonl \
  --reviews gold_sets/general/review.jsonl \
  --annotator argilla
uv run python -m shared.goldsets.cli status \
  --seed gold_sets/general/seed.jsonl \
  --annotated gold_sets/general/annotated.jsonl \
  --reviews gold_sets/general/review.jsonl
```

Expected: review validation is clean and status prints `candidates=40 submitted=10 approved=10 rejected=0`. If any record is rejected, replace/correct and re-review it before loading; never relabel rejection as approval without a new independent check.

- [ ] **Step 10: Test-load then development-load the immutable slice**

Resetting the test DB is permitted because it is test-only:

```bash
/Library/PostgreSQL/17/bin/psql -h /tmp -d ai_experiments_test -U huiliang -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
uv run python -m shared.db.migrations apply --test
uv run python -m shared.goldsets.cli load \
  --file gold_sets/general/annotated.jsonl \
  --version general-slice-v0.0 \
  --sha general-slice-reviewed-2026-07-18 \
  --test
uv run python -m shared.goldsets.cli load \
  --file gold_sets/general/annotated.jsonl \
  --version general-slice-v0.0 \
  --sha general-slice-reviewed-2026-07-18
```

Expected: each first load reports 10. A repeated identical load reports an idempotent no-op.

- [ ] **Step 11: Destroy Argilla and verify zero residual resources**

```bash
terraform -chdir=infra/gcp/annotation destroy -auto-approve -input=false
gcloud compute instances list --project adept-prod-497323
gcloud compute disks list --project adept-prod-497323
gcloud compute addresses list --project adept-prod-497323
gcloud storage buckets list --project adept-prod-497323
```

Expected: destroy succeeds and all inventories are empty. Do not proceed to reporting while any recovery-created resource remains.

- [ ] **Step 12: Record the result and calibration decision**

Replace `Status: not yet run` in the experiment README with exact candidate/submitted/approved/rejected/rubric/load counts, validation output, development version, teardown result, and final inventory. State that judge calibration remains blocked because 10 examples are below the 100-200 double-annotated requirement.

Change experiment 0003 to `done` only if all acceptance criteria pass. Otherwise keep it `running` and record the exact failed gate.

- [ ] **Step 13: Run final local verification**

```bash
uv run pytest -q
uv run ruff check .
git diff --check
git status --short
```

Expected: tests and Ruff pass; only intended README/index changes are tracked; private annotated/review JSONL and tfvars do not appear.

- [ ] **Step 14: Commit public evidence only**

```bash
git add experiments/0003-eval-general-curation-slice/README.md EXPERIMENTS.md
git commit -m "docs: record reviewed general-lane curation slice"
```
