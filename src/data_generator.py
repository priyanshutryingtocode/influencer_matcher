"""Synthetic influencer database.

Stands in for a real data source. Swap generate_influencers() out for a
function that reads from your influencer platform's API or your own
database, and nothing downstream (embeddings, retrieval, ranking) needs to
change, as long as you still return a list of Influencer objects.
"""

import random

from .models import Influencer

NICHES = {
    "Sustainable fashion": ["thrifted", "slow fashion", "eco", "capsule wardrobe", "secondhand"],
    "Fitness & wellness": ["strength training", "mobility", "recovery", "nutrition", "running"],
    "Beauty & skincare": ["clean beauty", "skincare routine", "makeup tutorial", "dermatology", "K-beauty"],
    "Food & cooking": ["weeknight meals", "baking", "vegan", "meal prep", "street food"],
    "Travel": ["budget travel", "van life", "solo travel", "luxury stays", "backpacking"],
    "Tech & gadgets": ["unboxing", "productivity apps", "smart home", "reviews", "AI tools"],
    "Personal finance": ["budgeting", "investing basics", "side hustles", "debt payoff", "FIRE"],
    "Parenting": ["toddler life", "postpartum", "family travel", "meal ideas", "sleep training"],
    "Gaming": ["speedruns", "indie games", "streaming setup", "reviews", "esports"],
    "Home & interiors": ["small space living", "DIY", "thrifted decor", "renovation", "plants"],
}

PLATFORMS = ["Instagram", "TikTok", "YouTube"]
CITIES = ["Austin", "Toronto", "Manchester", "Lagos", "Bangalore", "Melbourne", "Berlin", "Mexico City", "Seoul", "Lisbon"]
ADJ = ["daily", "the", "real", "modern", "wild", "quiet", "curious", "honest", "little", "urban"]
NOUN = ["desk", "kitchen", "trail", "notebook", "studio", "closet", "garden", "loop", "corner", "signal"]


def generate_influencers(count: int = 60, seed: int = 42) -> list[Influencer]:
    """Deterministic (seeded) synthetic dataset, so results are reproducible
    across runs while you're developing."""
    rng = random.Random(seed)
    influencers = []
    for i in range(count):
        niche_name = rng.choice(list(NICHES.keys()))
        tag_pool = NICHES[niche_name]
        tags = rng.sample(tag_pool, k=rng.randint(2, 3))
        followers = round(8000 * (1 + rng.random() * 60) ** 1.6)
        engagement = round(1 + rng.random() * 6.5, 1)
        rate = round((followers / 1000) * (15 + rng.random() * 40) * (0.7 + rng.random() * 0.8) / 50) * 50
        handle = f"@{rng.choice(ADJ)}.{rng.choice(NOUN)}{rng.randint(1, 99)}"
        city = rng.choice(CITIES)
        influencers.append(
            Influencer(
                id=i,
                handle=handle,
                niche=niche_name,
                platform=rng.choice(PLATFORMS),
                city=city,
                followers=followers,
                engagement=engagement,
                rate=rate,
                tags=tags,
                bio=f"{niche_name} creator covering {', '.join(tags)}. Based in {city}.",
            )
        )
    return influencers
