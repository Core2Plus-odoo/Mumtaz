"""Vendored specialist agent definitions, read as knowledge.

The library under ``data/agent_library/`` is 14 markdown personas from the MIT
licensed agency-agents project (see NOTICE there) — nine sales specialists and
five finance ones. Each is 180-270 lines of framework: signal tiers, discovery
structures, pipeline maths, objection handling.

The whole point of this module is that we do **not** embed that wholesale. All
fourteen files come to roughly 25,000 tokens; pasted into six role prompts they
would dwarf C2P's own playbooks and bury the standard-first discipline the
product exists to enforce. So :func:`digest` returns what the other knowledge
modules return — a compact reference: who each specialist is, and the skeleton
of the frameworks they carry. An agent that needs a specialist's full method can
ask for it by slug via :func:`full`.

Read at import, cached in memory. The files are in git and change only when
somebody deliberately refreshes them.
"""

import logging
import os
import re

_logger = logging.getLogger(__name__)

LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "agent_library")

DIVISIONS = ("sales", "finance")

# How much of each specialist survives into a prompt-sized digest.
_DESC_CHARS = 150
_MAX_HEADINGS = 7
_HEADING_CHARS = 46

# Every file upstream follows the same template, so these headings appear in all
# fourteen and distinguish nothing. Spending prompt budget on them would say
# "this agent has a core mission" nine times over. What survives is the
# distinctive method — MEDDPICC, signal tiering, the pipeline maths.
_BOILERPLATE_HEADINGS = (
    "your identity",
    "identity & memory",
    "your core mission",
    "core mission",
    "role definition",
    "core capabilities",
    "critical rules",
    "your technical deliverables",
    "technical deliverables",
    "workflow process",
    "your workflow",
    "success metrics",
    "quality standards",
)

_CACHE = {}


def _parse(path):
    """Split one agent file into its frontmatter and body.

    Hand-parsed rather than via PyYAML: the frontmatter is four or five flat
    ``key: value`` lines, and this module should not add a dependency to the
    delivery API for that.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        _logger.warning("agent_library: cannot read %s (%s)", path, exc)
        return None

    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            body = parts[2]
            for line in parts[1].splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip():
                    meta[key.strip()] = value.strip().strip('"').strip("'")

    slug = os.path.splitext(os.path.basename(path))[0]
    return {
        "slug": slug,
        "name": meta.get("name") or slug.replace("-", " ").title(),
        "description": meta.get("description", ""),
        "vibe": meta.get("vibe", ""),
        "headings": re.findall(r"^##\s+(.+?)\s*$", body, re.MULTILINE),
        "body": body.strip(),
    }


def load(division):
    """Every parsed agent in a division, sorted by slug. Cached."""
    if division in _CACHE:
        return _CACHE[division]
    folder = os.path.join(LIBRARY_DIR, division)
    agents = []
    if os.path.isdir(folder):
        for filename in sorted(os.listdir(folder)):
            if filename.endswith(".md"):
                parsed = _parse(os.path.join(folder, filename))
                if parsed:
                    agents.append(parsed)
    if not agents:
        _logger.warning(
            "agent_library: no agents found in %s — prompts will fall back to "
            "C2P's own playbooks only", folder
        )
    _CACHE[division] = agents
    return agents


def full(slug):
    """One specialist's complete method, for an agent that needs the depth.

    Returns an empty string when the slug is unknown, so a caller that guesses
    wrong degrades to its built-in knowledge rather than raising mid-generation.
    """
    for division in DIVISIONS:
        for agent in load(division):
            if agent["slug"] == slug:
                return agent["body"]
    _logger.info("agent_library: no vendored agent with slug %r", slug)
    return ""


def _line(agent):
    description = agent["description"]
    if len(description) > _DESC_CHARS:
        description = description[:_DESC_CHARS].rstrip() + "…"
    distinctive = [
        h for h in agent["headings"]
        if not h.lower().strip().startswith(_BOILERPLATE_HEADINGS)
    ]
    # If a file is nothing but the template, an empty framework list is more
    # honest than falling back to boilerplate that says nothing.
    headings = [h[:_HEADING_CHARS] for h in distinctive[:_MAX_HEADINGS]]
    line = "- %s [%s]: %s" % (agent["name"], agent["slug"], description)
    if headings:
        line += "\n  Frameworks: " + "; ".join(headings)
    return line


def digest(division):
    """Compact reference to a division's specialists, for prompt embedding."""
    agents = load(division)
    if not agents:
        return ""
    header = (
        "%s SPECIALIST LIBRARY (%s agents, vendored — see "
        "data/agent_library/NOTICE).\nThese are reference methods, not "
        "instructions: C2P's own playbook and the standard-first ladder win "
        "wherever they disagree. Call agent_library.full(slug) for a "
        "specialist's complete method.\n"
        % (division.upper(), len(agents))
    )
    return header + "\n".join(_line(agent) for agent in agents)


def catalog():
    """Every specialist, for the console and for callers choosing a slug."""
    return {
        division: [
            {
                "slug": a["slug"],
                "name": a["name"],
                "description": a["description"],
                "vibe": a["vibe"],
                "sections": len(a["headings"]),
            }
            for a in load(division)
        ]
        for division in DIVISIONS
    }
