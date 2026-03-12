# QE Framework Migration Tool — Architecture Document

> Version 3.0 | Framework-Agnostic | Stack: Python · FastAPI · LangChain/LangGraph · SQLite · React

---

## 1. System Goal

Build a **framework-agnostic, LLM-assisted QE test automation migration system** capable of converting any source automation framework to any target automation framework — incrementally, traceably, and in a defined target folder structure.

**Canonical Example:**
```
Java + Selenium + TestNG  →  TypeScript + Playwright
```

The system handles any source → target pair without any code changes — all framework knowledge lives in swappable Ruleset YAML files.

---

## 2. Two Migration Phases, One Pipeline

The system operates in two phases, but they share **one identical LangGraph pipeline**. The pipeline is simply invoked twice with different inputs.

```
Phase 1 — Infrastructure Migration
  Input:  All non-test files (page objects, utilities, base classes, config, constants)
  Registry state at start:  empty
  Pipeline invocations:  one per file, in topological dependency order

Phase 2 — Test Case Migration
  Input:  One selected test file (+ any unresolved dependencies)
  Registry state at start:  fully populated from Phase 1
  Pipeline invocations:  one per selected test (or small batch)
```

Inside the pipeline, the nodes behave identically for both phases. The Planner checks the State Registry before every decision — in Phase 2, most dependencies are already migrated so they are skipped. This is handled automatically, not by separate logic.

**Why one pipeline and not two?**
- All migration logic lives in one place — bugs fixed once, improvements applied everywhere
- The distinction between "infra file" and "test file" is just a classification difference, not a pipeline difference
- Phase 2 naturally builds on Phase 1 because the State Registry is shared

---

## 3. Two Distinct Analysis Concepts

The word "analyze" is used for two completely different operations in this system. They must not be confused.

### 3.1 Source Repository Analysis (One-Time, Upfront)

This is a **heavy, one-time scan** of the entire source repository. It runs before any migration begins and produces all the structured data that the pipeline will consume.

**What it does:**
- Walks the entire source repository
- Parses every file's AST using Tree-sitter
- Classifies every file by role (test, page object, utility, base class, config, etc.)
- Builds the full dependency graph across all files
- Resolves the target output path for every file (from the Ruleset)
- Creates all migration units in the database
- Computes topological sort (migration order)
- Estimates total LLM token cost

**Output:** Fully populated SQLite database. This output is static — it does not change as migration progresses.

**Triggered by:** `POST /projects/{id}/analyze` — runs once, result displayed to engineer before migration starts.

---

### 3.2 PrepareContext Node (Per-File, Inside the Pipeline)

This is a **lightweight DB read** that runs at the start of each pipeline invocation. It does not scan or parse anything — all parsing was done in Source Repository Analysis.

**What it does:**
- Reads the current migration unit's data from the DB (already computed)
- Fetches signatures of its dependencies from already-migrated files (State Registry)
- Checks which dependencies are already migrated (to skip them)
- Assembles a clean context object and hands it to the Planner node

**It is named "PrepareContext" not "Analyze"** because it prepares context — it does not perform analysis.

---

### 3.3 Relationship Between the Two

```
Source Repository Analysis
  └── Runs once on the entire repo
  └── AST parsing, classification, graph building, path resolution
  └── All results stored in SQLite
           │
           ▼
    SQLite Database (static, fully populated)
           │
           ▼
  PrepareContext Node (runs per file, inside LangGraph pipeline)
    └── Reads from DB — lightweight
    └── Assembles context for Planner
    └── No parsing, no scanning
```

---

## 4. Core Design Principles

### 4.1 Framework-Agnostic via Ruleset DSL

Zero hardcoded framework knowledge in application logic. All framework-specific knowledge lives in versioned, schema-validated YAML **Rulesets**:

- File role classification patterns
- Target folder structure and naming conventions
- Pattern mappings (source API → target API)
- Lifecycle hook mappings
- Import transformations
- Forbidden patterns in target output
- Target framework properties (async, module system, etc.)

Adding a new framework pair = authoring a new Ruleset YAML. No code changes.

---

### 4.2 Target Folder Structure Defined in the Ruleset

The target repository's complete folder structure is a first-class section of the Ruleset (`target_structure` block). This means:

- The folder layout is versioned alongside the migration rules
- Target file paths are resolved **deterministically during Source Repository Analysis** — before any LLM call
- The Generator always receives a fixed `target_path` as an instruction — it never invents paths
- Teams with different folder conventions can supply project-level `structure_overrides` without forking the Ruleset

---

### 4.3 Deterministic + LLM Hybrid

Every decision is handled at the lowest cost, highest reliability layer available.

| Concern | Handler |
|---|---|
| File discovery | Deterministic (filesystem scan) |
| AST parsing | Deterministic (Tree-sitter) |
| Import resolution | Deterministic (graph traversal) |
| Dependency ordering | Deterministic (topological sort) |
| File role classification | Ruleset patterns + heuristics |
| Target path resolution | Deterministic (Ruleset `target_structure`) |
| Migration action decision | Hybrid: Ruleset rules → heuristics → LLM fallback |
| Code generation | LLM (structured prompt + ruleset context) |
| State lookup | Deterministic (SQLite) |

---

### 4.4 Minimal Context Strategy

LLM context is assembled surgically — the system never sends the entire repository to the LLM.

**Per generation call, the context contains:**
1. Condensed Migration Ruleset (pattern mappings, hooks, conventions)
2. Migrated inventory from State Registry (target paths + import aliases of already-migrated files)
3. Signatures only (not full code) of the current file's dependencies
4. Full source code of the file being migrated

The Context Builder enforces a configurable per-call token budget. If dependency signatures exceed the budget, it trims to direct dependencies only, then to method-name-only signatures if still over.

---

### 4.5 State Registry as Source of Truth

The State Registry is the persistent memory of the migration, stored in SQLite. It enables:

- Knowing what's already migrated (skip it in subsequent pipeline calls)
- Providing exact target import aliases to the Generator (no hallucinated imports)
- Preventing duplicate utility generation across files
- Token cost tracking across the full project
- Full audit trail of every generation attempt and outcome

---

### 4.6 LangGraph for Agentic Orchestration

The migration pipeline is a **LangGraph stateful graph** — not a linear script. Each pipeline step is a discrete node. Conditional edges route between nodes based on outcomes.

Benefits:
- **Resumable** — LangGraph checkpointing means any crash resumes from the last completed node
- **Inspectable** — every node's input and output is logged
- **Extensible** — new capabilities (e.g. validation, HITL gates) are added as new nodes without restructuring existing flow

---

## 5. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         React Frontend                            │
│   Project Setup | Analysis View | Migration Feed | Cost Tracker   │
└────────────────────────────┬─────────────────────────────────────┘
                             │ REST + SSE
┌────────────────────────────▼─────────────────────────────────────┐
│                    FastAPI — API Layer                             │
│  /projects  /analyze  /migrate  /status  /export  /rulesets       │
└────────────────────────────┬─────────────────────────────────────┘
                             │
           ┌─────────────────┴──────────────────────┐
           ▼                                         ▼
┌──────────────────────┐              ┌──────────────────────────┐
│  Source Repository   │              │   Migration Engine        │
│  Analysis Service    │              │   (LangGraph Pipeline)    │
│                      │              │                           │
│  • File Discovery    │              │   ┌──────────────────┐   │
│  • AST Parsing       │  populates   │   │  PrepareContext  │   │
│  • Classification    │──────────▶  │   └────────┬─────────┘   │
│  • Dependency Graph  │   SQLite     │            │              │
│  • Path Resolution   │              │   ┌────────▼─────────┐   │
│  • Migration Units   │              │   │     Planner      │   │
└──────────────────────┘              │   └────────┬─────────┘   │
                                      │            │              │
                                      │   ┌────────▼─────────┐   │
                                      │   │    Generator     │   │
                                      │   └────────┬─────────┘   │
                                      │            │              │
                                      │   ┌────────▼─────────┐   │
                                      │   │     Commit       │   │
                                      │   └──────────────────┘   │
                                      └──────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                         Core Services                              │
│  AST Parser · Dependency Graph · File Classifier · Context Builder │
│  Ruleset Engine · Target Path Resolver · State Registry            │
└────────────────────────────┬─────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          LLM API         SQLite        File System
      (via LangChain)  (SQLAlchemy)
```

---

## 6. The LangGraph Pipeline

### 6.1 Pipeline Nodes

```
PrepareContext  →  Planner  →  Generator  →  Commit
```

| Node | Type | Responsibility |
|---|---|---|
| **PrepareContext** | Deterministic | Read migration unit from DB, fetch dependency signatures, check registry, assemble context object |
| **Planner** | Hybrid | Determine migration action (migrate / split / merge / absorb) using Ruleset rules → heuristics → LLM fallback |
| **Generator** | LLM | Call LLM with surgical context, parse output, store generated code and token usage |
| **Commit** | Deterministic | Write generated file(s) to exact target paths, update State Registry |

### 6.2 Pipeline State

```python
class MigrationState(TypedDict):
    project_id:        str
    current_unit:      MigrationUnit   # the file being migrated
    source_code:       str
    context:           GenerationContext
    planned_action:    str             # migrate | split | merge | absorb
    generated_code:    dict[str, str]  # target_path → code
```

### 6.3 LangGraph Graph Definition

```python
graph = StateGraph(MigrationState)

graph.add_node("prepare_context", prepare_context_node)
graph.add_node("plan",            planner_node)
graph.add_node("generate",        generator_node)
graph.add_node("commit",          commit_node)

graph.add_edge("prepare_context", "plan")
graph.add_edge("plan",            "generate")
graph.add_edge("generate",        "commit")
graph.add_edge("commit",          END)

graph.set_entry_point("prepare_context")
compiled = graph.compile(checkpointer=SqliteSaver(...))
```

### 6.4 How the Pipeline Serves Both Phases

The pipeline is called once per migration unit. The caller (Pipeline Runner) controls which units are fed in and in what order.

```python
# Phase 1 — Infrastructure
for unit in get_infra_units_in_topological_order(project_id):
    pipeline.invoke({ "project_id": project_id, "current_unit": unit })

# Phase 2 — Test migration (called per user selection)
def migrate_test(project_id, test_file_id):
    deps = get_unresolved_dependencies(test_file_id, project_id)
    for dep_unit in topological_order(deps):
        pipeline.invoke({ "project_id": project_id, "current_unit": dep_unit })
    test_unit = get_unit(test_file_id)
    pipeline.invoke({ "project_id": project_id, "current_unit": test_unit })
```

---

## 7. Migration Ruleset — The Framework DSL

### 7.1 Full Ruleset Schema

```yaml
ruleset:
  id: java-selenium-testng__to__typescript-playwright
  version: "1.0"
  source:
    language: java
    test_framework: testng
    automation_library: selenium
  target:
    language: typescript
    test_framework: playwright
    automation_library: playwright

# ── TARGET FOLDER STRUCTURE ──────────────────────────────────────
# Defines the complete folder layout of the generated target repo.
# Every file role maps to an exact folder path.
# Target paths are resolved during Source Repo Analysis — before
# any LLM call is made.
# ─────────────────────────────────────────────────────────────────
target_structure:
  root: "."
  folders:
    test_file:    "tests"
    page_object:  "src/pages"
    utility:      "src/utils"
    base_class:   "src/base"
    config:       "."
    constants:    "src/constants"
    fixtures:     "src/fixtures"
    types:        "src/types"

  naming_convention:
    test_file:    "{kebab-name}.spec.ts"     # LoginTest   → login.spec.ts
    page_object:  "{kebab-name}.page.ts"     # LoginPage   → login.page.ts
    utility:      "{kebab-name}.ts"          # WaitUtils   → wait-utils.ts
    base_class:   "{kebab-name}.ts"          # BaseTest    → base-test.ts
    config:       "playwright.config.ts"
    constants:    "{kebab-name}.ts"
    fixtures:     "index.ts"
    types:        "index.d.ts"

  index_files:
    # Roles for which a barrel index.ts is auto-generated
    - page_object
    - utility
    - fixtures

# ── FILE ROLE CLASSIFICATION ──────────────────────────────────────
file_roles:
  test_file:
    patterns: ["**/*Test.java", "**/*Spec.java"]
    annotations: ["@Test", "@Suite"]
  page_object:
    patterns: ["**/pages/**/*.java"]
    base_class_hint: "BasePage"
  utility:
    patterns: ["**/utils/**/*.java", "**/helpers/**/*.java"]
  base_class:
    patterns: ["**/base/**/*.java"]
  config:
    patterns: ["testng.xml", "*.properties", "**/config/**/*.java"]
  constants:
    patterns: ["**/constants/**/*.java", "**/enums/**/*.java"]

# ── LIFECYCLE HOOK MAPPINGS ───────────────────────────────────────
lifecycle_hooks:
  "@BeforeSuite":  "test.beforeAll"
  "@AfterSuite":   "test.afterAll"
  "@BeforeMethod": "test.beforeEach"
  "@AfterMethod":  "test.afterEach"
  "@BeforeClass":  "test.beforeAll"
  "@AfterClass":   "test.afterAll"

# ── PATTERN MAPPINGS ──────────────────────────────────────────────
pattern_mappings:
  - source: "driver.findElement(By.id(\"{val}\"))"
    target: "page.locator('#{val}')"
  - source: "driver.findElement(By.xpath(\"{val}\"))"
    target: "page.locator(\"{val}\")"
  - source: "driver.findElement(By.cssSelector(\"{val}\"))"
    target: "page.locator(\"{val}\")"
  - source: "@FindBy(id = \"{val}\")"
    target: "page.locator('#{val}')"
  - source: "driver.get(\"{val}\")"
    target: "await page.goto(\"{val}\")"
  - source: "element.click()"
    target: "await element.click()"
  - source: "element.sendKeys(\"{val}\")"
    target: "await element.fill(\"{val}\")"
  - source: "Assert.assertEquals({a}, {b})"
    target: "expect({a}).toBe({b})"
  - source: "Assert.assertTrue({a})"
    target: "expect({a}).toBeTruthy()"

# ── IMPORT MAPPINGS ───────────────────────────────────────────────
import_mappings:
  "org.openqa.selenium.*":      "@playwright/test"
  "org.testng.annotations.*":   "@playwright/test"
  "org.testng.Assert":          "@playwright/test"

# ── TARGET FRAMEWORK PROPERTIES ──────────────────────────────────
target_properties:
  async_required: true
  module_system: "esm"
  strict_mode: true
  test_runner_config: "playwright.config.ts"
```

### 7.2 Project-Level Structure Override

Teams with non-standard folder layouts pass `structure_overrides` at project creation:

```json
{
  "structure_overrides": {
    "folders": {
      "page_object": "e2e/pages",
      "test_file":   "e2e/tests",
      "utility":     "e2e/helpers"
    }
  }
}
```

The Ruleset Engine merges overrides with the base `target_structure` at runtime.

### 7.3 Ruleset Registry

```
backend/app/rulesets/
  java-selenium-testng__to__typescript-playwright.yaml
  python-selenium-pytest__to__typescript-playwright.yaml
  javascript-wdio__to__typescript-playwright.yaml
```

Custom rulesets can be uploaded via `POST /rulesets`. The Ruleset Engine validates the schema with Pydantic before storing.

---

## 8. Target Path Resolution

Target paths are resolved **once, during Source Repository Analysis**, and stored in the `migration_units` table. The Generator never decides or invents paths.

**Resolution algorithm:**

```
1. role  →  target_structure.folders[role]
   e.g.  "page_object"  →  "src/pages"

2. source filename  →  strip role suffix, convert to kebab-case
   e.g.  "LoginPage.java"  →  "login"

3. apply naming_convention[role] template
   e.g.  "{kebab-name}.page.ts"  →  "login.page.ts"

4. compose full path
   root / folder / filename  →  "./src/pages/login.page.ts"

5. derive import alias
   e.g.  "@pages/login.page"

6. store both in migration_units table
```

---

## 9. State Registry — Database Schema

### 9.1 Tables

```sql
-- projects
id, name, source_path, target_path, ruleset_id,
structure_overrides_json, status, created_at, updated_at

-- files
id, project_id, source_path, role, checksum, ast_summary_json

-- migration_units
id, project_id, source_file_id, action (migrate|split|merge|absorb),
target_path, import_alias, status (pending|generating|migrated|failed),
iteration, created_at, updated_at

-- dependencies
id, project_id, from_file_id, to_file_id, dependency_type

-- generations
id, migration_unit_id, attempt_number, prompt_tokens, completion_tokens,
generated_code, llm_model, created_at
```

### 9.2 Key Queries

```sql
-- Is this file already migrated?
SELECT status FROM migration_units WHERE source_file_id = ? AND project_id = ?;

-- Import alias for a migrated dependency
SELECT import_alias, target_path FROM migration_units
WHERE source_file_id = ? AND status = 'migrated';

-- All files that depend on a given file
SELECT f.source_path FROM dependencies d
JOIN files f ON f.id = d.from_file_id
WHERE d.to_file_id = ? AND d.project_id = ?;

-- Total token cost for project
SELECT SUM(prompt_tokens + completion_tokens) FROM generations g
JOIN migration_units mu ON mu.id = g.migration_unit_id
WHERE mu.project_id = ?;
```

---

## 10. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + TypeScript | Dashboard, analysis view, migration feed |
| API | FastAPI (Python) | REST endpoints, SSE streaming |
| Agentic Workflow | LangGraph | Stateful pipeline, conditional edges, checkpointing |
| LLM Abstraction | LangChain | Provider-agnostic LLM calls, prompt templates, output parsers |
| LLM Provider | OpenAI (default, swappable) | GPT-4o for generation, GPT-4o-mini for planning |
| AST Parsing | Tree-sitter (Python bindings) | Multi-language grammar support |
| Database | SQLite via SQLAlchemy | Migration state, audit trail |
| Dependency Graph | NetworkX | Topological sort, graph traversal |
| Ruleset Config | YAML + Pydantic | Schema-validated, human-readable framework DSL |

---

## 11. Non-Functional Considerations

**Resumability** — LangGraph checkpoints allow any pipeline failure to resume from the last completed node. No re-work on restart.

**Cost Control** — All LLM calls record token usage in the `generations` table. A pre-migration cost estimate is produced after Source Repository Analysis, before any LLM call is made.

**Observability** — Every LangGraph node emits structured SSE events streamed to the frontend in real time.

**Extensibility** — Validation tiers and HITL review gates are planned future additions. They slot in as new LangGraph nodes between `generate` and `commit` with no changes to existing nodes.

**Multi-model** — LangChain's model abstraction allows switching LLM provider via environment variable.
