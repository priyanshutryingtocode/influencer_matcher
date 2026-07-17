"""LLM ranking step: asks Gemini to pick and justify the best candidates
from the retrieved pool. Uses response_schema for structured, directly
parseable JSON output rather than hoping the model follows a text format."""

import json

from google import genai
from google.genai import types

from . import config
from .models import Brief, Influencer

RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "rationale"],
            },
        }
    },
    "required": ["ranked"],
}


def _build_prompt(brief: Brief, candidates: list[Influencer], top_n: int) -> str:
    candidate_payload = [
        {
            "id": c.id,
            "handle": c.handle,
            "niche": c.niche,
            "platform": c.platform,
            "followers": c.followers,
            "engagement_rate": c.engagement,
            "rate_usd": c.rate,
            "tags": c.tags,
            "bio": c.bio,
        }
        for c in candidates
    ]

    return f"""You are ranking candidate creators for a brand campaign.

Brand brief:
- Niche: {brief.niche}
- Platform: {brief.platform}
- Budget per creator (max): ${brief.budget_max}
- Target audience: {brief.audience or "not specified"}
- Vibe / tone: {brief.vibe or "not specified"}

Candidates:
{json.dumps(candidate_payload, indent=2)}

Pick the best {top_n} candidates for this brief. For each, write a one-sentence
rationale (under 25 words) that is specific to this brief -- not a generic
restatement of their bio."""


def rank_candidates(
    client: genai.Client,
    brief: Brief,
    candidates: list[Influencer],
    top_n: int = 5,
) -> list[dict]:
    response = client.models.generate_content(
        model=config.GEN_MODEL,
        contents=_build_prompt(brief, candidates, top_n),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RANKING_SCHEMA,
        ),
    )
    parsed = json.loads(response.text)
    return parsed["ranked"]
