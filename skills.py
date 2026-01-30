import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_SCRIPT_TIMEOUT = 60


@dataclass
class SkillMetadata:
    """Represents an Agent Skill with metadata parsed from SKILL.md frontmatter.

    see: AgentSkills Specification: https://agentskills.io/specification

    """

    name: str
    description: str
    path: str  # Absolute path to the skill directory
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: Optional[str] = None


def parse_skill_frontmatter(skill_md_path: str) -> Optional[SkillMetadata]:
    """
    Parse the YAML frontmatter from a SKILL.md file.
    Returns a Skill object with metadata, or None if parsing fails.
    """
    try:
        with open(skill_md_path, mode="r", encoding="utf-8") as f:
            content = f.read()

        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not frontmatter_match:
            return None

        frontmatter_yaml = frontmatter_match.group(1)
        frontmatter = yaml.safe_load(frontmatter_yaml)

        if not frontmatter:
            return None

        # Required fields
        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name or not description:
            return None

        # Validate name format (lowercase, hyphens, no consecutive hyphens)
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            return None

        skill_dir = str(Path(skill_md_path).parent)

        return SkillMetadata(
            name=name,
            description=description,
            path=skill_dir,
            license=frontmatter.get("license"),
            compatibility=frontmatter.get("compatibility"),
            metadata=frontmatter.get("metadata", {}),
            # allowed_tools=frontmatter.get("allowed-tools"),
        )

    except Exception as e:
        logger.warning(f"Failed to parse skill at {skill_md_path}: {e}")
        return None


def discover_skills(skill_directories: List[str]) -> List[SkillMetadata]:
    """
    Discover skills from configured directories.
    A skill is a folder containing a SKILL.md file.

    Args:
        skill_directories: List of directory paths to scan for skills

    Returns:
        List of discovered Skill objects with parsed metadata
    """
    skills = []

    for skill_root_dir in skill_directories:
        skill_path = Path(skill_root_dir)

        if not skill_path.exists() or not skill_path.is_dir():
            logger.warning(
                f"Skill root directory does not exist or is not a directory, skipping: {skill_root_dir}"
            )
            continue
        for skill_dir in skill_path.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            skill = parse_skill_frontmatter(str(skill_md))
            if skill:
                skills.append(skill)
    return skills


def skills_to_xml(skills: List[SkillMetadata]) -> str:
    """
    Generate XML representation of available skills for system prompt injection.
    Follows the agentskills specification format.

    Args:
        skills: List of Skill objects

    Returns:
        XML string for inclusion in system prompt
    """
    if not skills:
        return ""

    lines = ["<available_skills>"]
    for skill in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{skill.name}</name>")
        # Escape XML special characters in description
        escaped_desc = (
            skill.description.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        lines.append(f"    <description>{escaped_desc}</description>")
        skill_md_path = str(Path(skill.path) / "SKILL.md")
        lines.append(f"    <location>{skill_md_path}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")

    return "\n".join(lines)


def build_skills_system_prompt(skills: List[SkillMetadata]) -> str:
    """
    Build the system prompt section for skills.

    Args:
        skills: List of available Skill objects

    Returns:
        System prompt text including skill instructions and available skills XML
    """
    if not skills:
        return ""

    skills_xml = skills_to_xml(skills)

    return f"""
<agent_skills>
Skills are pre-defined workflows for specific tasks like web search, data scraping, etc.

**How to use skills:**
1. Use `load_skill_file` tool to read the skill's `SKILL.md` for full instructions
2. Follow the instructions and use `execute_script` tool to run skill scripts
3. Do not load the same file multiple times

**Available skills:**
{skills_xml}
</agent_skills>
"""


def build_tool_functions_prompt(tool_functions: list) -> str:
    """
    Build system prompt section describing tool functions.

    Args:
        tool_functions: List of tool function objects

    Returns:
        System prompt text describing tool functions
    """
    if not tool_functions:
        return ""

    # Group tools by category based on function name prefix
    categories = {}
    for func in tool_functions:
        name = func.__name__
        if name.startswith("browser_"):
            category = "browser"
        else:
            category = "general"

        if category not in categories:
            categories[category] = []
        categories[category].append(name)

    lines = ["<tool_functions>"]
    lines.append("Direct function tools available for immediate use:")
    lines.append("")

    if "browser" in categories:
        lines.append("**Browser Tools** (persistent browser session):")
        lines.append("- Use for web page interaction: navigation, clicking, typing, screenshots")
        lines.append("- Browser state persists across calls (cookies, login sessions maintained)")
        lines.append("- Use `browser_snapshot` to get page structure and element references")
        lines.append("- Use element `ref` from snapshot for click/type operations")
        lines.append(f"- Available: {', '.join(categories['browser'])}")
        lines.append("")

    if "general" in categories:
        lines.append("**General Tools:**")
        lines.append(f"- {', '.join(categories['general'])}")
        lines.append("")

    lines.append("</tool_functions>")
    return "\n".join(lines)


def build_unified_tools_prompt(
    tool_functions: list, skills: List[SkillMetadata]
) -> str:
    """
    Build unified system prompt for all tools (tool functions + skills).

    Args:
        tool_functions: List of tool function objects
        skills: List of SkillMetadata objects

    Returns:
        Complete tools system prompt
    """
    tool_prompt = build_tool_functions_prompt(tool_functions)
    skills_prompt = build_skills_system_prompt(skills)

    if not tool_prompt and not skills_prompt:
        return ""

    sections = []

    sections.append("""<tools_guide>
You have access to two types of tools:

1. **Tool Functions**: Direct Python functions for immediate operations (e.g., browser control)
2. **Skills**: Pre-packaged workflows for complex tasks (e.g., web search, scraping)

**When to use which:**
- Use **Tool Functions** for direct operations that need state persistence (browser sessions)
- Use **Skills** for pre-defined workflows with scripts (google-search, wiki-search, scrape_website)

**General guidelines:**
- All tool calls must include full, self-contained context (tools have no memory between calls)
- Avoid vague queries; each tool call should retrieve specific, actionable information
- For historical content, use archived webpage search tools
- Extract all useful information from tool results before proceeding
</tools_guide>
                    
# General Objective

You accomplish a given task iteratively, breaking it down into clear steps and working through them methodically.

## Task Strategy

1. Analyze the user's request and set clear, achievable sub-goals. Prioritize these sub-goals in a logical order.
2. Start with a concise, numbered, step-by-step plan (e.g., 1., 2., 3.) outlining how you will solve the task before taking any action. Each sub-goal should correspond to a distinct step in your task-solving process.
3. Work through these sub-goals sequentially. After each step, carefully review and extract all potentially relevant information, details, or implications from the tool result before proceeding. The user may provide tool-use feedback, reflect on the results, and revise your plan if needed. If you encounter new information or challenges, adjust your approach accordingly. Revisit previous steps to ensure earlier sub-goals or clues have not been overlooked or missed.
4. You have access to a wide range of powerful tools. Use them strategically to accomplish each sub-goal.

## Multi-Source Research Strategy (CRITICAL)

**For any factual question requiring web research, you MUST follow this research protocol:**

1. **Search Phase**: Use google-search to find relevant sources (get at least 5-10 URLs)
2. **Multi-Source Analysis Phase**:
   - You MUST visit and analyze AT LEAST 3 different webpages before drawing conclusions
   - Use `browser_navigate` to visit each webpage sequentially
   - Use `browser_snapshot` to read page content and extract key information
   - Record findings from each source separately
3. **Cross-Validation Phase**:
   - After visiting multiple sources, compare all findings
   - Identify: agreements (facts confirmed by multiple sources), conflicts (contradictory information), uncertainties
   - Note which sources support which claims
4. **Synthesis Phase**:
   - Only after analyzing multiple sources, synthesize the findings
   - Present all candidate answers with their supporting evidence
   - Clearly document any conflicting information or remaining uncertainties

**IMPORTANT**: Do NOT conclude after visiting only one webpage. Always visit multiple sources to verify information.

## Tool-Use Guidelines

1. **IMPORTANT: Each step must involve exactly ONE tool call only, unless the task is already solved. You are strictly prohibited from making multiple tool calls in a single response.** 
2. Before each tool call:
- Briefly summarize and analyze what is currently known.
- Identify what is missing, uncertain, or unreliable.
- Be concise; do not repeat the same analysis across steps.
- Choose the most relevant tool for the current sub-goal, and explain why this tool is necessary at this point.
- Verify whether all required parameters are either explicitly provided or can be clearly and reasonably inferred from context.
- Do not guess or use placeholder values for missing inputs.
- Skip optional parameters unless they are explicitly specified.
3. All tool queries must include full, self-contained context. Tools do not retain memory between calls. Include all relevant information from earlier steps in each query.
4. Avoid broad, vague, or speculative queries. Every tool call should aim to retrieve new, actionable information that clearly advances the task.
5. **For historical or time-specific content**: Regular search engines return current webpage content, not historical content. Archived webpage search is essential for retrieving content as it appeared in the past, use related tools to search for the historical content.
6. Even if a tool result does not directly answer the question, thoroughly extract and summarize all partial information, important details, patterns, constraints, or keywords that may help guide future steps. Never proceed to the next step without first ensuring that all significant insights from the current result have been fully considered.

## Tool-Use Communication Rules

1. **CRITICAL: After issuing exactly ONE tool call, STOP your response immediately. You must never make multiple tool calls in a single response. Do not include tool results, do not assume what the results will be, and do not continue with additional analysis or tool calls. The user will provide the actual tool results in their next message.**
2. Do not present the final answer until the entire task is complete.
3. Do not mention tool names.
4. Do not engage in unnecessary back-and-forth or end with vague offers of help. Do not end your responses with questions or generic prompts.
5. Do not use tools that do not exist.
6. Unless otherwise requested, respond in the same language as the user's message.
7. If the task does not require tool use, answer the user directly.
""")

    if tool_prompt:
        sections.append(tool_prompt)
    if skills_prompt:
        sections.append(skills_prompt)

    return "\n".join(sections)

class SkillIntegrationTools:
    """
    Provide tools that used for skill integration, including:

    - load_skill_file: Load a file from a skill directory, such as `SKILL.md` or other files in the skill directory.
    - execute_script: Execute a script provided by the skill, such as `python scripts/now.py`.
    """

    def __init__(self, skills: List[SkillMetadata]) -> None:
        self.skills = {skill.name: skill for skill in skills}

    def load_skill_file(self, skill_name: str, file_path: str = "SKILL.md") -> str:
        """
        Load a file from a skill directory.

        Args:
            skill_name (str): The name of the skill, must be one of the available skills.
            file_path (str): The path to the file to load, default is `SKILL.md`

        Returns:
            str: The content of the file or an error message.
        """
        try:
            skill_root = Path(self.skills[skill_name].path).resolve()
            target_path = (skill_root / file_path).resolve()

            if not target_path.is_relative_to(skill_root):
                return f"Error: Access denied. File '{file_path}' is outside the skill directory."

            if not target_path.exists():
                return f"Error: File '{file_path}' not found in skill '{skill_name}'."

            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            logger.warning(
                f"Failed to load file {file_path} from skill {skill_name}: {str(e)}",
                exc_info=True,
            )
            return f"Error: Failed to load file {file_path} from skill {skill_name}: {str(e)}"

    def execute_script(self, skill_name: str, command: str) -> str:
        """
        Execute a script provided by the skill (synchronous version).

        Args:
            skill_name (str): The name of the skill.
            command (str): The shell command to execute.

        Returns:
            str: The stdout and stderr of the script execution.
        """
        try:
            skill_root = Path(self.skills[skill_name].path).resolve()

            try:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=skill_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=DEFAULT_SCRIPT_TIMEOUT,
                    text=True,
                    errors="replace",
                )
            except subprocess.TimeoutExpired:
                return "<stdout></stdout><stderr>Error: Execution timed out.</stderr>"

            stdout_str = (completed.stdout or "").strip()
            stderr_str = (completed.stderr or "").strip()

            logger.info(f"Executed script {command} in skill {skill_name} successfully")

            return (
                f"<stdout>\n{stdout_str}\n</stdout>\n"
                f"<stderr>\n{stderr_str}\n</stderr>"
            )

        except Exception as e:
            logger.warning(
                f"Failed to execute script {command} in skill {skill_name}: {str(e)}",
                exc_info=True,
            )
            return f"<stdout></stdout><stderr>System Error: {str(e)}</stderr>"
