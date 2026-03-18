import json
import logging
import shutil
import os
from pathlib import Path
from typing import Any, Dict, List

from services.llm.agent_service import BaseLLMAgentService
from models.planner_models import PlannerOutputSchema, PlanUnit
from services.generator.prompts import ROLE_PROMPTS, DEFAULT_PROMPT

logger = logging.getLogger(__name__)


class CodeGeneratorService:
    """
    Executes the migration plan by generating code using LLMs or performing file operations.
    """

    def __init__(self, source_repo_path: Path, target_repo_path: Path):
        self.source_repo_path = source_repo_path
        self.target_repo_path = target_repo_path

    def generate_code(self, plan_payload: Dict[str, Any], context_payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processes the Planner plan and generates target codebase files.
        """
        logger.info("Starting Code Generation process...")

        try:
            plan = PlannerOutputSchema(**plan_payload)
        except Exception as e:
            logger.error(f"Failed to validate plan in Generator: {e}")
            raise ValueError(f"Invalid plan format for code generation: {e}")

        # Generate Scaffolding/Build Files IF metadata is present
        scaffolding_results = {}
        if context_payload:
            scaffolding_results = self._generate_build_files(context_payload)

        results = {
            "processed_units": 0,
            "actions_summarized": {
                "copy": 0,
                "migrate": 0,
                "skip": 0,
                "analyze_only": 0,
                "merge": 0,
                "split": 0,
                "errors": 0
            },
            "failures": [],
            "scaffolding": scaffolding_results
        }

        # Order units by execution_order if provided
        units_to_process = plan.plan_units
        if plan.execution_order:
            ordered_units = []
            unit_map = {u.plan_unit_id: u for u in plan.plan_units}
            for uid in plan.execution_order:
                if uid in unit_map:
                    ordered_units.append(unit_map[uid])
            # Add any units not in execution order just in case
            for u in plan.plan_units:
                if u.plan_unit_id not in plan.execution_order:
                    ordered_units.append(u)
            units_to_process = ordered_units

        logger.info(f"Processing {len(units_to_process)} plan units.")

        for unit in units_to_process:
            logger.info(f"Processing Unit {unit.plan_unit_id} (Decision: {unit.decision})")
            decision = unit.decision.lower()

            try:
                if decision == "copy":
                    self._handle_copy(unit, results)
                elif decision == "analyze_only":
                    results["actions_summarized"]["analyze_only"] += 1
                elif decision == "skip":
                    results["actions_summarized"]["skip"] += 1
                elif decision in ("migrate", "merge", "split"):
                    self._handle_generation(unit, results)
                else:
                    logger.warning(f"Unknown decision type '{unit.decision}' for unit {unit.plan_unit_id}")
                    results["actions_summarized"]["errors"] += 1
                
                results["processed_units"] += 1

            except Exception as e:
                logger.error(f"Error processing unit {unit.plan_unit_id}: {e}")
                results["actions_summarized"]["errors"] += 1
                results["failures"].append({
                    "plan_unit_id": unit.plan_unit_id,
                    "error": str(e)
                })

        return results

    def _handle_copy(self, unit: PlanUnit, results: Dict[str, Any]):
        """Handles physical file copy without LLM."""
        source_paths = unit.source_paths
        target_paths = unit.target_paths_final

        if not source_paths or not target_paths:
            raise ValueError(f"Missing paths for copy operation in unit {unit.plan_unit_id}")

        for src, tgt in zip(source_paths, target_paths):
            src_full = self.source_repo_path / src
            tgt_full = self.target_repo_path / tgt

            if not src_full.exists():
                logger.warning(f"Source file {src_full} does not exist for copy.")
                continue

            # Ensure target directory exists
            tgt_full.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Copying {src_full} to {tgt_full}")
            try:
                shutil.copy2(src_full, tgt_full)
                results["actions_summarized"]["copy"] += 1
            except Exception as e:
                logger.error(f"Failed to copy {src} to {tgt}: {e}")
                raise

    def _handle_generation(self, unit: PlanUnit, results: Dict[str, Any]):
        """Handles single or multiple file logic generation with LLM."""
        decision_map_key = "merge" if unit.decision.lower() == "merge" else ("split" if unit.decision.lower() == "split" else "migrate")
        
        source_paths = unit.source_paths
        target_paths = unit.target_paths_final

        if not source_paths or not target_paths:
            raise ValueError(f"Paths missing for generation in unit {unit.plan_unit_id}")

        # Enforce N -> N mapping: 1 file = 1 LLM call
        for src, tgt in zip(source_paths, target_paths):
            src_full = self.source_repo_path / src
            tgt_full = self.target_repo_path / tgt

            if not src_full.exists():
                logger.warning(f"Source file {src_full} does not exist for generation.")
                continue

            logger.info(f"[LLM] Converting {src} -> {tgt}")
            
            # Read Source
            source_content = src_full.read_text(encoding="utf-8")
            
            # Build Prompt
            role = unit.role or unit.target_role or "default"
            instructions = ROLE_PROMPTS.get(role.lower(), DEFAULT_PROMPT)
            
            converted_code = self._call_llm_for_conversion(
                source_content=source_content,
                instructions=instructions,
                source_path=src,
                target_path=tgt
            )

            # Write Target
            try:
                tgt_full.parent.mkdir(parents=True, exist_ok=True)
                tgt_full.write_text(converted_code, encoding="utf-8")
                results["actions_summarized"][decision_map_key] += 1
            except Exception as e:
                logger.error(f"Failed to write target file {tgt}: {e}")
                raise

    def _call_llm_for_conversion(self, source_content: str, instructions: str, source_path: str, target_path: str) -> str:
        """Invokes BaseLLMAgentService to convert single file content."""
        system_prompt = (
            "You are an expert software engineer specializing in converting Java/Selenium code into TypeScript/Playwright code.\n"
            "Your layout MUST follow the instructions provided strictly.\n\n"
            "CRITICAL: Output ONLY the converted code. "
            "Do not wrap your output in markdown formatting (like ```typescript), do not provide any explanation, preamble, or notes. "
            "Your response must containing ONLY code starting from the imports and ending at the last statement."
        )

        agent = BaseLLMAgentService(
            system_prompt=system_prompt,
            tools=[],  # No tools needed for single file generation
            model="gpt-4o",  # Using good model for code conversion
            temperature=0.1,  # Low temperature for deterministic generation
            max_retries=2
        )

        prompt_input = (
            f"### Role-Specific Instructions:\n{instructions}\n\n"
            f"### Context:\n"
            f"Source File: {source_path}\n"
            f"Target File: {target_path}\n\n"
            f"### Source Code:\n"
            f"```\n"
            f"{source_content}\n"
            f"```\n"
        )

        response = agent.invoke_with_metadata(prompt_input)
        output = response["output"]

        # Post-processing to clean up any accidental markdown tags
        cleaned = self._clean_llm_output(output)
        return cleaned

    @staticmethod
    def _clean_llm_output(output: str) -> str:
        """Removes code block wrappers if modern models fail to comply."""
        candidate = output.strip()
        if candidate.startswith("```"):
            # Find the first newline and last ```
            lines = candidate.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]  # Remove ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove trailing ```
            candidate = "\n".join(lines).strip()
        return candidate

    def _generate_build_files(self, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generates configuration files (package.json, tsconfig.json, playwright.config.ts)."""
        logger.info("Generating build configuration files...")
        
        context = context_payload.get("context", {})
        metadata = context.get("repository_metadata", {})
        
        # Look for source build file to read
        build_content = ""
        source_build_files = ["pom.xml", "build.gradle", "build.gradle.kts"]
        for bf in source_build_files:
            bf_path = self.source_repo_path / bf
            if bf_path.exists():
                logger.info(f"Using source build file {bf} for dependency mapping.")
                build_content = bf_path.read_text(encoding="utf-8")
                break
                
        system_prompt = (
            "You are an expert devops and setup agent for Playwright automation frameworks.\n"
            "Your job is to generate root level configuration files for migrating a framework into TypeScript/Playwright.\n\n"
            "CRITICAL: Output ONLY a single raw JSON object that maps filenames to contents. "
            "Do NOT include markdown block wrappers (like ```json), explanations, or notes. "
            "Your output must be IMMEDIATELY parsable by json.loads()."
        )

        agent = BaseLLMAgentService(
            system_prompt=system_prompt,
            tools=[],
            model="gpt-4o",
            temperature=0.1,
            max_retries=2
        )

        prompt_input = (
            f"### Target Settings:\n"
            f"Target Framework: {metadata.get('target_framework', 'Playwright')}\n"
            f"Target Language: {metadata.get('target_language', 'TypeScript')}\n"
            f"Target Test Engine: {metadata.get('target_test_engine', '@playwright/test')}\n\n"
            f"### Source Build Config Context:\n"
            f"```\n"
            f"{build_content if build_content else 'No build file found'}\n"
            f"```\n\n"
            f"### Output Requirements:\n"
            "Return a single JSON object with the following schema:\n"
            "{\n"
            '  "package.json": "content mapping dependencies and run scripts suitable for a modern playwright project with type: module if desired",\n'
            '  "tsconfig.json": "proper tsconfig contents",\n'
            '  "playwright.config.ts": "playwright config setup with responsive timeouts, reporting setups etc"\n'
            "}\n"
            "The values must be the RAW FILE CONTENTS as strings."
        )

        try:
            # We use invoke_json ensuring valid format
            response_json = agent.invoke_json(prompt_input)
            generated_files = {}

            # Write files to target repo root
            for filename, content in response_json.items():
                if filename not in ["package.json", "tsconfig.json", "playwright.config.ts"]:
                    continue # Safety check
                    
                target_path = self.target_repo_path / filename
                logger.info(f"Writing scaffolding file: {filename}")
                target_path.write_text(content, encoding="utf-8")
                generated_files[filename] = "created"

            return {
                "generated": generated_files,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Failed to generate build scaffolding files: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
