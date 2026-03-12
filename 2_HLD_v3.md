# QE Framework Migration Tool — High Level Design (HLD)

> Version 3.0 | Stack: Python · FastAPI · LangChain/LangGraph · SQLite · React

---

## 1. System Overview

The QE Framework Migration Tool converts QE automation repositories between any framework pair using an LLM-assisted agentic pipeline. The system operates in two phases (infrastructure first, tests second) but uses **one shared pipeline** for both. All framework knowledge — including the target folder structure — lives in swappable Ruleset YAML files.

---

## 2. High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  React Frontend                                                      │
│  ┌──────────────┐ ┌────────────────────┐ ┌──────────┐ ┌─────────┐  │
│  │ Project Setup│ │  Analysis Dashboard│ │Migration │ │  Cost   │  │
│  │              │ │  (graph + plan)    │ │   Feed   │ │ Tracker │  │
│  └──────────────┘ └────────────────────┘ └──────────┘ └─────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST + SSE
┌──────────────────────────────▼──────────────────────────────────────┐
│  FastAPI — API Layer                                                  │
│                                                                       │
│  POST /projects                  POST /projects/{id}/analyze          │
│  POST /projects/{id}/migrate     GET  /projects/{id}/status  (SSE)   │
│  GET  /projects/{id}/analysis    GET  /projects/{id}/export           │
│  GET  /projects/{id}/graph       GET  /projects/{id}/cost             │
│  GET  /rulesets                  POST /rulesets                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                          ▼
┌─────────────────────────┐          ┌──────────────────────────────┐
│  Source Repository      │          │  Migration Engine             │
│  Analysis Service       │          │  (LangGraph Pipeline)        │
│                         │          │                              │
│  One-time, full repo    │ populates│  Runs per migration unit     │
│  scan. Produces all     │─────────▶│                              │
│  structured data before │  SQLite  │  PrepareContext              │
│  migration begins.      │          │       ↓                      │
│                         │          │    Planner                   │
│  • File Discovery       │          │       ↓                      │
│  • AST Parsing          │          │   Generator                  │
│  • Classification       │          │       ↓                      │
│  • Dependency Graph     │          │    Commit                    │
│  • Path Resolution      │          │                              │
│  • Migration Units      │          └──────────────────────────────┘
└─────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│  Core Services                                                        │
│                                                                       │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │  AST Parser  │  │ Dependency Graph  │  │    Context Builder     │ │
│  │ (Tree-sitter)│  │ Builder (NetworkX)│  │                        │ │
│  └──────────────┘  └──────────────────┘  └────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │    File      │  │    Ruleset       │  │    State Registry      │ │
│  │  Classifier  │  │    Engine        │  │                        │ │
│  └──────────────┘  └──────────────────┘  └────────────────────────┘ │
│  ┌──────────────┐                                                     │
│  │ Target Path  │                                                     │
│  │  Resolver    │                                                     │
│  └──────────────┘                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
            LLM API         SQLite        File System
        (via LangChain)  (SQLAlchemy)
```

---

## 3. Source Repository Analysis Service

**Triggered by:** `POST /projects/{id}/analyze`
**Runs:** Once per project, before migration starts
**Output:** Fully populated SQLite database — static, does not change during migration

This is the heaviest operation in the system. It runs entirely deterministically — no LLM is involved.

### Processing Steps

```
Step 1 — File Discovery
  Walk source repo directory tree
  Apply include/exclude globs from Ruleset file_roles
  Produce: raw file list

Step 2 — AST Parsing  (Tree-sitter, per file)
  Extract:
    - Class names
    - Method names + signatures (name, params, return type)
    - Annotations / decorators
    - Import statements
    - Inheritance (extends / implements)
    - Complexity score (AST node count)
  Store: ast_summary_json in files table

Step 3 — File Classification
  For each file, apply in priority order:
    1. Annotation match       (@Test → test_file)
    2. Ruleset path pattern   (**/pages/** → page_object)
    3. Base class inference   (extends BasePage → page_object)
    4. Naming heuristic       (*Utils.java → utility)
  Store: role in files table

Step 4 — Dependency Graph  (NetworkX)
  For each file: resolve imports to actual files within the repo
  Build directed graph: FileA → FileB  (A depends on B)
  Compute: topological sort → migration order
  Detect: circular dependencies (log warning, continue)
  Store: all edges in dependencies table

Step 5 — Target Path Resolution  (Ruleset Engine)
  For each file:
    role + source filename → target folder + target filename
    derive import alias
  Store: target_path, import_alias in migration_units table

Step 6 — Migration Unit Creation
  One migration_unit row per file
  Fields: source_file_id, action (TBD by Planner), target_path,
          import_alias, status=pending, iteration order

Step 7 — Repository Summary
  File counts by role
  Dependency graph statistics
  Estimated token cost (signature-based heuristic)
```

### Output Surfaces to Engineer

After analysis completes, the frontend shows:
- Full file list with assigned roles and resolved target paths
- Interactive dependency graph (ReactFlow)
- Migration order (topological sequence)
- Token cost estimate
- Any classification warnings (unknown role, circular dependency)

The engineer reviews this before starting migration.

---

## 4. Migration Engine — LangGraph Pipeline

### 4.1 Overview

The pipeline is a LangGraph stateful graph with four nodes:

```
PrepareContext  →  Planner  →  Generator  →  Commit
```

It is invoked once per migration unit. The **Pipeline Runner** (orchestration service) calls it repeatedly — once per file in Phase 1, once per selected test (plus its unresolved deps) in Phase 2.

---

### 4.2 Node: PrepareContext

**Type:** Deterministic (no LLM)

**Responsibility:** Read everything needed for this migration unit from the DB and assemble a `GenerationContext` object.

```python
def prepare_context_node(state: MigrationState) -> MigrationState:
    unit = state["current_unit"]

    # 1. Load full source code from filesystem
    source_code = read_file(unit.source_file.path)

    # 2. Get already-migrated inventory from State Registry
    migrated_inventory = registry.get_migrated_inventory(project_id)
    #    → list of { source_path, target_path, import_alias }

    # 3. Get dependency signatures (not full code)
    dep_signatures = []
    for dep in unit.dependencies:
        if registry.is_migrated(dep.source_path):
            dep_signatures.append(registry.get_signatures(dep.source_path))

    # 4. Load ruleset
    ruleset = ruleset_engine.load(project.ruleset_id)

    # 5. Assemble and return context
    state["source_code"] = source_code
    state["context"] = GenerationContext(
        ruleset=ruleset,
        migrated_inventory=migrated_inventory,
        dependency_signatures=dep_signatures,
        source_code=source_code,
        target_path=unit.target_path,
        action=unit.action,
    )
    return state
```

---

### 4.3 Node: Planner

**Type:** Hybrid — Ruleset rules → heuristics → LLM fallback

**Responsibility:** Confirm or update the migration action for the current unit. The Analyzer pre-assigns a default action; the Planner refines it with more detailed logic.

**Decision logic:**

```
1. Already migrated? (State Registry check)
   → status: skip, exit pipeline early

2. Ruleset has a direct action rule for this role?
   e.g. role=config → action: absorb
   → apply directly

3. Heuristics (deterministic)
   Method count > threshold AND methods span multiple domains?  → split
   File < 10 lines of real logic?                              → absorb
   Multiple source files share same target output path?        → merge

4. Ambiguous? → LLM fallback (GPT-4o-mini)
   Prompt: file AST summary + target framework conventions
   Output: { action, rationale, target_paths }

5. Update migration_unit.action in DB
   Update state["planned_action"]
```

**Actions:**

| Action | Description | Example |
|---|---|---|
| `migrate` | 1 source → 1 target file | `LoginPage.java` → `src/pages/login.page.ts` |
| `split` | 1 source → N target files | `Utils.java` → `wait.ts` + `data-helpers.ts` |
| `merge` | N sources → 1 target file | Multiple enums → `src/constants/index.ts` |
| `absorb` | Source folds into framework config | `DriverFactory.java` → `playwright.config.ts` |

---

### 4.4 Node: Generator

**Type:** LLM (GPT-4o via LangChain)

**Responsibility:** Call the LLM with surgical context and produce target framework code.

**Prompt structure:**

```
┌────────────────────────────────────────────────────────────────┐
│ SYSTEM                                                          │
│   You are a {source_lang} to {target_lang} migration expert.   │
│   Output ONLY valid {target_lang} code.                        │
│   No explanations. No markdown fences.                         │
│   Follow the migration rules exactly.                          │
├────────────────────────────────────────────────────────────────┤
│ BLOCK 1 — Migration Ruleset                                     │
│   Pattern mappings, lifecycle hooks, import mappings,          │
│   target framework idioms, naming conventions                  │
├────────────────────────────────────────────────────────────────┤
│ BLOCK 2 — Migrated Inventory                                    │
│   source_file → target_path + import_alias                     │
│   (for all already-migrated files, from State Registry)        │
├────────────────────────────────────────────────────────────────┤
│ BLOCK 3 — Dependency Signatures                                 │
│   Class/method signatures of this file's dependencies          │
│   (signatures only — not full source code)                     │
├────────────────────────────────────────────────────────────────┤
│ BLOCK 4 — Source File                                           │
│   Full source code of the file being migrated                  │
├────────────────────────────────────────────────────────────────┤
│ INSTRUCTION                                                     │
│   Migrate the source file above.                               │
│   Write to: {target_path}                                      │
│   Action: {action}                                             │
│   {action-specific instructions}                               │
└────────────────────────────────────────────────────────────────┘
```

**Action-specific instruction variants:**

- `migrate` — single file output
- `split` — output multiple files separated by `=== FILE: {path} ===`
- `merge` — Block 4 contains all N source files; output is one merged file
- `absorb` — Block 4 contains the source; output is only the relevant config section to emit

**Output parsing:**
- Standard LangChain output parser for `migrate` and `absorb`
- Custom multi-file parser for `split`
- Result: `dict[target_path → generated_code]`

**All recorded in DB:** prompt tokens, completion tokens, model, generated code, attempt number.

---

### 4.5 Node: Commit

**Type:** Deterministic (no LLM)

**Responsibility:** Write generated files to disk and update the State Registry.

```python
def commit_node(state: MigrationState) -> MigrationState:
    for target_path, code in state["generated_code"].items():
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        # Write generated file
        write_file(target_path, code)

    # Update State Registry
    registry.mark_migrated(
        unit=state["current_unit"],
        target_paths=list(state["generated_code"].keys()),
    )

    # Emit SSE event
    emit_event("file_migrated", file=unit.source_path, targets=target_paths)

    return state
```

This is the **only node that writes to the filesystem**.

---

### 4.6 LangGraph Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

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

compiled_pipeline = graph.compile(
    checkpointer=SqliteSaver.from_conn_string("./migration.db")
)
```

---

### 4.7 Pipeline Runner — Orchestrating Both Phases

The Pipeline Runner is the orchestration service that calls the pipeline in the correct order for each phase.

```python
class PipelineRunner:

    async def run_phase_1(self, project_id: str):
        """Migrate all infrastructure files in topological order."""
        units = db.get_infra_units_ordered(project_id)  # topological sort
        for unit in units:
            if registry.is_migrated(unit.source_file_id):
                continue  # already done (resume scenario)
            await compiled_pipeline.ainvoke(
                {"project_id": project_id, "current_unit": unit},
                config={"configurable": {"thread_id": unit.id}}
            )

    async def run_phase_2(self, project_id: str, test_file_id: str):
        """Migrate a selected test and any unresolved dependencies."""
        # Resolve dependency tree for this test
        all_deps = graph_service.get_full_dependency_tree(test_file_id)

        # Filter to only unresolved (not yet migrated)
        unresolved = [d for d in all_deps if not registry.is_migrated(d.id)]

        # Migrate unresolved deps first (topological order)
        for dep_unit in topological_order(unresolved):
            await compiled_pipeline.ainvoke(
                {"project_id": project_id, "current_unit": dep_unit},
                config={"configurable": {"thread_id": dep_unit.id}}
            )

        # Migrate the test itself
        test_unit = db.get_unit(test_file_id)
        await compiled_pipeline.ainvoke(
            {"project_id": project_id, "current_unit": test_unit},
            config={"configurable": {"thread_id": test_unit.id}}
        )
```

---

## 5. Ruleset Engine

The central service that loads, validates, and provides query methods over Ruleset YAML files. All other components depend on it.

```python
class RulesetEngine:
    def load(self, ruleset_id: str) -> Ruleset
    def list_available(self) -> list[RulesetSummary]
    def validate_schema(self, raw_yaml: dict) -> Ruleset
    def match_file_role(self, file_path: str, ast_data: ASTResult) -> str
    def resolve_target_path(self, role: str, source_name: str,
                             overrides: dict | None = None) -> str
    def get_import_alias(self, target_path: str) -> str
    def get_lifecycle_mapping(self, annotation: str) -> str | None
    def get_pattern_mappings(self) -> list[PatternMapping]
```

**`resolve_target_path` algorithm:**

```python
def resolve_target_path(self, role, source_name, overrides=None):
    structure = merge(self.ruleset.target_structure, overrides or {})

    folder = structure["folders"][role]
    template = structure["naming_convention"][role]
    base_name = to_kebab_case(strip_role_suffix(source_name))
    filename = template.replace("{kebab-name}", base_name)

    return os.path.join(structure["root"], folder, filename)
```

---

## 6. Context Builder

Assembles LLM prompt context for Generator calls, enforcing a per-call token budget.

```python
class ContextBuilder:

    def build_generation_context(
        self,
        unit: MigrationUnit,
        registry: StateRegistry,
        ruleset: Ruleset,
        token_budget: int = 4000
    ) -> GenerationContext:

        used_tokens = 0

        # Block 1 — Ruleset (condensed)
        ruleset_block = condense_ruleset(ruleset)
        used_tokens += estimate_tokens(ruleset_block)

        # Block 2 — Migrated inventory
        inventory = registry.get_migrated_inventory(unit.project_id)
        inventory_block = format_inventory(inventory)
        used_tokens += estimate_tokens(inventory_block)

        # Block 3 — Dependency signatures (trim if over budget)
        dep_sigs = self._get_dep_signatures(unit, registry, token_budget - used_tokens)

        # Block 4 — Full source (always included)
        source_block = read_file(unit.source_file.path)

        return GenerationContext(
            ruleset_block=ruleset_block,
            inventory_block=inventory_block,
            dep_signatures=dep_sigs,
            source_code=source_block,
            target_path=unit.target_path,
            action=unit.action,
        )

    def _get_dep_signatures(self, unit, registry, remaining_budget):
        sigs = get_full_signatures(unit.direct_dependencies, registry)
        if estimate_tokens(sigs) <= remaining_budget:
            return sigs
        # Trim to direct deps only
        sigs = get_full_signatures(unit.direct_dependencies[:3], registry)
        if estimate_tokens(sigs) <= remaining_budget:
            return sigs
        # Trim to method names only
        return get_method_names_only(unit.direct_dependencies, registry)
```

---

## 7. State Registry

```python
class StateRegistry:
    def is_migrated(self, source_file_id: str) -> bool
    def get_import_alias(self, source_file_id: str) -> str | None
    def get_migrated_inventory(self, project_id: str) -> list[MigratedFile]
    def get_signatures(self, source_file_id: str) -> FileSignatures
    def get_token_cost(self, project_id: str) -> TokenCostSummary
    def mark_migrated(self, unit: MigrationUnit, target_paths: list[str]) -> None
    def mark_failed(self, unit: MigrationUnit, error: str) -> None
```

---

## 8. API Layer

### 8.1 Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects` | Create project (source path, ruleset, overrides) |
| POST | `/projects/{id}/analyze` | Trigger source repo analysis (async) |
| GET | `/projects/{id}/analysis` | Return analysis result (files, graph, units, cost estimate) |
| GET | `/projects/{id}/graph` | Dependency graph JSON for ReactFlow |
| POST | `/projects/{id}/migrate/phase1` | Start Phase 1 — infra migration |
| POST | `/projects/{id}/migrate/phase2` | Start Phase 2 — migrate selected test |
| GET | `/projects/{id}/status` | SSE stream — live pipeline progress |
| GET | `/projects/{id}/cost` | Token usage and cost summary |
| GET | `/projects/{id}/export` | Download target repo as zip |
| GET | `/rulesets` | List available rulesets |
| POST | `/rulesets` | Upload and validate custom ruleset |

### 8.2 SSE Event Schema

```json
{
  "event":        "file_migrated",
  "file":         "LoginPage.java",
  "target_path":  "src/pages/login.page.ts",
  "action":       "migrate",
  "tokens_used":  1240,
  "phase":        1,
  "timestamp":    "2025-01-15T10:23:45Z"
}
```

Event types: `analysis_complete`, `phase_started`, `file_started`, `file_migrated`, `file_failed`, `phase_complete`

---

## 9. Frontend Views

| View | Purpose |
|---|---|
| **Project Setup** | Source repo path, ruleset selection, structure overrides input |
| **Analysis Dashboard** | File list (role + target path), ReactFlow dependency graph, migration order, token estimate |
| **Migration Feed** | SSE-streamed real-time per-file progress, phase progress bar, running token cost |
| **Cost Tracker** | Token usage per file and per phase, bar chart (Recharts), estimated dollar cost |
| **Export** | Download target repo zip, view migration summary |

---

## 10. End-to-End Data Flow

```
1. Engineer creates project
   └── source_path, ruleset_id, optional structure_overrides

2. Source Repository Analysis (one-time)
   └── Scans repo → AST → classify → dependency graph → path resolution
   └── Populates: files, dependencies, migration_units tables
   └── Engineer reviews result in Analysis Dashboard

3. Phase 1 — Infrastructure Migration
   PipelineRunner iterates infra units in topological order:
     For each unit:
       PrepareContext  →  reads DB, assembles context
       Planner         →  confirms/refines action
       Generator       →  LLM call, produces code
       Commit          →  writes file, updates State Registry

4. Phase 1 complete
   └── All infra files written to target folder structure
   └── State Registry: all infra import aliases populated

5. Phase 2 — Test Migration (per selected test)
   PipelineRunner:
     └── Resolve dependency tree for selected test
     └── Filter to unresolved only
     └── Run pipeline for unresolved deps (same 4 nodes)
     └── Run pipeline for the test file

6. Repeat Phase 2 for each test the team wants to migrate

7. Export
   └── Zip target directory → download
   └── migration_report.json included (file map, token cost, status)
```

---

## 11. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| One pipeline or two? | One, invoked twice | Identical logic; distinction is input set and registry state |
| "Analyze" node name | Renamed to **PrepareContext** | Accurately reflects its role — it reads DB, not scans repo |
| Target path resolution timing | During Source Repo Analysis | All paths known before LLM is called; eliminates hallucinated paths |
| LLM for path decisions | Never | Paths are deterministic from Ruleset; LLM receives path as a fixed input |
| Target folder structure location | Ruleset YAML `target_structure` block | Versioned with rules; project-level overrides supported |
| Validation in pipeline | Not in current version | Planned addition as new nodes between `generate` and `commit` |
| HITL gates | Not in current version | Planned future optimisation — slots in cleanly as new LangGraph nodes |
