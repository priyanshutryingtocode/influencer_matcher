"""Seeded Faker profiles for development, demos, and retrieval evaluation."""

import random

from faker import Faker

from .models import Influencer

NICHES = {
    "Fashion": ["streetwear", "luxury", "minimalist", "outfits", "vintage"],
    "Sustainable Fashion": ["thrifted", "eco", "capsule wardrobe", "slow fashion", "secondhand"],
    "Fitness": ["strength", "gym", "running", "HIIT", "calisthenics"],
    "Yoga": ["mindfulness", "stretching", "mobility", "breathwork", "wellness"],
    "Nutrition": ["meal prep", "protein", "healthy recipes", "macros", "diet"],
    "Beauty": ["makeup", "skincare", "clean beauty", "fragrance", "K-beauty"],
    "Hair Care": ["curly hair", "styling", "hair growth", "products", "salon"],
    "Food": ["recipes", "baking", "street food", "restaurants", "desserts"],
    "Coffee": ["espresso", "latte art", "cafes", "beans", "brewing"],
    "Travel": ["solo travel", "budget", "luxury", "backpacking", "digital nomad"],
    "Technology": ["AI", "gadgets", "reviews", "smart home", "productivity"],
    "Programming": ["Python", "JavaScript", "C++", "algorithms", "system design"],
    "Gaming": ["FPS", "RPG", "esports", "streaming", "indie games"],
    "Photography": ["portraits", "landscape", "editing", "film", "gear"],
    "Videography": ["cinematography", "drone", "editing", "storytelling", "gear"],
    "Finance": ["investing", "stocks", "budgeting", "crypto", "FIRE"],
    "Business": ["startups", "marketing", "sales", "leadership", "productivity"],
    "Education": ["study tips", "science", "career", "history", "math"],
    "Books": ["fiction", "authors", "reading", "reviews", "non-fiction"],
    "Music": ["guitar", "piano", "covers", "DJ", "production"],
    "Pets": ["dogs", "cats", "training", "nutrition", "rescue"],
    "Parenting": ["toddlers", "family", "activities", "education", "newborn"],
    "Home Decor": ["DIY", "plants", "renovation", "minimalism", "interiors"],
    "Luxury Lifestyle": ["cars", "watches", "travel", "fashion", "hotels"],
    "Automotive": ["EVs", "supercars", "reviews", "motorcycles", "mods"],
    "Science": ["space", "physics", "biology", "research", "AI"],
    "Art": ["digital art", "painting", "illustration", "watercolor", "design"],
    "Comedy": ["sketches", "memes", "satire", "standup", "parody"],
    "Motivation": ["mindset", "discipline", "habits", "success", "quotes"],
    "Real Estate": ["property", "luxury homes", "architecture", "investing", "renting"],
}

CITY_COUNTRY = {
    "New York": "USA", "Austin": "USA", "Toronto": "Canada", "London": "UK",
    "Paris": "France", "Berlin": "Germany", "Madrid": "Spain", "Rome": "Italy",
    "Tokyo": "Japan", "Seoul": "South Korea", "Singapore": "Singapore", "Bangkok": "Thailand",
    "Mumbai": "India", "Bangalore": "India", "Sydney": "Australia", "Cape Town": "South Africa",
    "Lagos": "Nigeria", "Dubai": "UAE", "Mexico City": "Mexico", "Sao Paulo": "Brazil",
}
LOCALE_BY_COUNTRY = {
    "USA": "en_US", "Canada": "en_CA", "UK": "en_GB", "France": "fr_FR", "Germany": "de_DE",
    "Spain": "es_ES", "Italy": "it_IT", "Japan": "ja_JP", "South Korea": "ko_KR",
    "India": "en_IN", "Brazil": "pt_BR", "Mexico": "es_MX", "Australia": "en_AU",
}
LANGUAGES_BY_COUNTRY = {
    "USA": ["English"], "Canada": ["English", "French"], "UK": ["English"],
    "France": ["French"], "Germany": ["German"], "Spain": ["Spanish"], "Italy": ["Italian"],
    "Japan": ["Japanese"], "South Korea": ["Korean"], "India": ["Hindi", "English"],
    "Brazil": ["Portuguese"], "Mexico": ["Spanish"], "Thailand": ["Thai", "English"],
    "Singapore": ["English"], "Australia": ["English"], "South Africa": ["English"],
    "Nigeria": ["English"], "UAE": ["Arabic", "English"],
}
PLATFORMS = ["Instagram", "TikTok", "YouTube", "Threads", "X", "Pinterest", "LinkedIn", "Snapchat", "Twitch"]
CONTENT_STYLES = ["Educational", "Reviews", "Tutorials", "Lifestyle", "Entertainment", "Storytelling", "Vlogs"]
BRANDS = {
    "Technology": ["Apple", "Samsung", "Asus", "Lenovo", "NVIDIA"],
    "Photography": ["Canon", "Sony", "DJI", "Adobe"], "Fitness": ["Nike", "Adidas", "Gymshark"],
    "Travel": ["Airbnb", "Booking.com", "GoPro"], "Beauty": ["Sephora", "Nykaa"],
    "Programming": ["GitHub", "JetBrains", "DigitalOcean"],
}
BIOS = [
    "Helping people master {topics} through practical tips.",
    "Sharing daily inspiration about {topics}.",
    "Making {topics} simple and enjoyable.",
    "Reviews, tutorials, and honest experiences with {topics}.",
]


def _tier_metrics(rng: random.Random) -> tuple[int, float]:
    tier = rng.choices(["nano", "micro", "macro", "mega"], weights=[45, 35, 15, 5])[0]
    ranges = {
        "nano": ((1_000, 10_000), (7.0, 12.0)), "micro": ((10_001, 100_000), (4.0, 8.0)),
        "macro": ((100_001, 1_000_000), (2.5, 5.0)), "mega": ((1_000_001, 5_000_000), (1.2, 3.0)),
    }
    follower_range, engagement_range = ranges[tier]
    return rng.randint(*follower_range), round(rng.uniform(*engagement_range), 1)


def _profile_metrics(rng: random.Random, followers: int, engagement: float) -> tuple[int, int, int]:
    likes = max(1, round(followers * engagement / 100))
    views = max(likes, round(followers * rng.uniform(0.15, 1.4)))
    comments = min(likes, max(1, round(likes * rng.uniform(0.02, 0.08))))
    return views, likes, comments


def generate_influencers(count: int = 60, seed: int = 42) -> list[Influencer]:
    """Generate reproducible, internally consistent fake creator profiles."""
    rng = random.Random(seed)
    niches = list(NICHES)
    cities = list(CITY_COUNTRY)
    used_handles: set[str] = set()
    creators: list[Influencer] = []

    for creator_id in range(count):
        primary = rng.choice(niches)
        secondary = rng.sample([n for n in niches if n != primary], k=rng.choices([0, 1, 2], [55, 35, 10])[0])
        tags = rng.sample(NICHES[primary], k=3)
        for niche in secondary:
            tags.append(rng.choice(NICHES[niche]))

        followers, engagement = _tier_metrics(rng)
        views, likes, comments = _profile_metrics(rng, followers, engagement)
        city = rng.choice(cities)
        country = CITY_COUNTRY[city]
        profile_fake = Faker(LOCALE_BY_COUNTRY.get(country, "en_US"))
        profile_fake.seed_instance(seed * 10_000 + creator_id)
        handle = _unique_handle(profile_fake, rng, used_handles)
        name = profile_fake.name()
        brand_pool = [brand for niche in [primary, *secondary] for brand in BRANDS.get(niche, [])]
        if not brand_pool:
            brand_pool = [f"{primary} Collective", f"{primary} Studio"]
        collaborations = rng.sample(brand_pool, k=min(len(brand_pool), rng.randint(0, 3)))
        audience_country = country if rng.random() < 0.65 else CITY_COUNTRY[rng.choice(cities)]

        creators.append(Influencer(
            id=creator_id, name=name, handle=handle, niche=primary, secondary_niches=secondary,
            platform=rng.choice(PLATFORMS), city=city, country=country,
            language=rng.choice(LANGUAGES_BY_COUNTRY.get(country, ["English"])),
            followers=followers, engagement=engagement, average_views=views, average_likes=likes,
            average_comments=comments, verified=followers >= 500_000 and rng.random() < 0.4,
            posts_per_week=rng.randint(2, 14), account_age_years=rng.randint(1, 12),
            content_style=rng.choice(CONTENT_STYLES), audience_age=rng.choice(["13-17", "18-24", "25-34", "35-44"]),
            audience_gender=rng.choice(["60% Female", "55% Female", "55% Male", "62% Male"]),
            audience_country=audience_country, brand_collaborations=collaborations, tags=tags,
            bio=f"{name}. {rng.choice(BIOS).format(topics=', '.join([primary, *secondary]))} Based in {city}, {country}.",
        ))
    return creators


def _unique_handle(fake: Faker, rng: random.Random, used_handles: set[str]) -> str:
    while True:
        handle = f"@{fake.user_name().replace('_', '').lower()}{rng.randint(1, 999)}"
        if handle not in used_handles:
            used_handles.add(handle)
            return handle
