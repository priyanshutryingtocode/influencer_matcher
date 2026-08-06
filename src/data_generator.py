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


def generate_balanced_influencers(
    count: int = 60,
    seed: int = 42,
    min_per_niche: int = 5,
    min_per_niche_platform: int = 3,
) -> list[Influencer]:
    """Generate influencers with balanced distribution across niche × platform.

    min_per_niche_platform is configurable so the per-(niche, platform)
    coverage floor can be raised for denser retrieval pools (fewer top-k
    slots wasted on adjacent-vibe niches). Note it drives the minimum viable
    count: len(NICHES) * len(PLATFORMS) * min_per_niche_platform.

    Algorithm:
    1. First pass: allocate min_per_niche_platform to each (niche, platform) combo
    2. Second pass: fill remaining quota proportionally
    3. Shuffle final list to avoid ordering bias
    """
    rng = random.Random(seed)
    niches = list(NICHES)
    platforms = list(PLATFORMS)
    cities = list(CITY_COUNTRY)
    
    total_combos = len(niches) * len(platforms)
    min_total = min_per_niche_platform * total_combos
    
    if count < min_total:
        raise ValueError(
            f"count={count} too small for balanced generation. "
            f"Minimum required: {min_total} ({min_per_niche_platform} per {total_combos} combos)"
        )
    
    used_handles: set[str] = set()
    creators: list[Influencer] = []
    creator_id = 0
    
    # Track how many we've generated per niche and per (niche, platform)
    niche_counts: dict[str, int] = {n: 0 for n in niches}
    combo_counts: dict[tuple[str, str], int] = {(n, p): 0 for n in niches for p in platforms}
    
    # Pass 1: Ensure minimum per (niche, platform)
    for niche in niches:
        for platform in platforms:
            for _ in range(min_per_niche_platform):
                if creator_id >= count:
                    break
                inf = _create_single_influencer(
                    creator_id=creator_id,
                    rng=rng,
                    niches=niches,
                    cities=cities,
                    used_handles=used_handles,
                    primary_niche=niche,
                    platform=platform,
                )
                creators.append(inf)
                niche_counts[niche] += 1
                combo_counts[(niche, platform)] += 1
                creator_id += 1
    
    # Pass 2: Ensure minimum per niche (if not already met)
    for niche in niches:
        while niche_counts[niche] < min_per_niche and creator_id < count:
            platform = rng.choice(platforms)
            inf = _create_single_influencer(
                creator_id=creator_id,
                rng=rng,
                niches=niches,
                cities=cities,
                used_handles=used_handles,
                primary_niche=niche,
                platform=platform,
            )
            creators.append(inf)
            niche_counts[niche] += 1
            combo_counts[(niche, platform)] += 1
            creator_id += 1
    
    # Pass 3: Fill remaining quota proportionally
    remaining = count - creator_id
    if remaining > 0:
        # Create weighted list of combos based on current deficit
        combo_weights = []
        for niche in niches:
            for platform in platforms:
                combo = (niche, platform)
                # Weight inversely proportional to current count
                weight = 1.0 / (combo_counts[combo] + 1)
                combo_weights.append((combo, weight))
        
        # Normalize weights
        total_weight = sum(w for _, w in combo_weights)
        combo_probs = [(combo, w / total_weight) for combo, w in combo_weights]
        
        for _ in range(remaining):
            # Sample combo based on weights
            r = rng.random()
            cumsum = 0.0
            selected_combo = combo_probs[0][0]
            for combo, prob in combo_probs:
                cumsum += prob
                if r <= cumsum:
                    selected_combo = combo
                    break
            
            niche, platform = selected_combo
            inf = _create_single_influencer(
                creator_id=creator_id,
                rng=rng,
                niches=niches,
                cities=cities,
                used_handles=used_handles,
                primary_niche=niche,
                platform=platform,
            )
            creators.append(inf)
            niche_counts[niche] += 1
            combo_counts[(niche, platform)] += 1
            creator_id += 1
    
    # Shuffle to avoid ordering bias
    rng.shuffle(creators)
    
    # Reassign IDs after shuffle
    for i, inf in enumerate(creators):
        inf.id = i
    
    return creators


def _create_single_influencer(
    creator_id: int,
    rng: random.Random,
    niches: list[str],
    cities: list[str],
    used_handles: set[str],
    primary_niche: str,
    platform: str,
) -> Influencer:
    """Create a single influencer with specified niche and platform."""
    secondary = rng.sample([n for n in niches if n != primary_niche], k=rng.choices([0, 1, 2], [55, 35, 10])[0])
    tags = rng.sample(NICHES[primary_niche], k=3)
    for niche in secondary:
        tags.append(rng.choice(NICHES[niche]))

    followers, engagement = _tier_metrics(rng)
    views, likes, comments = _profile_metrics(rng, followers, engagement)
    city = rng.choice(cities)
    country = CITY_COUNTRY[city]
    profile_fake = Faker(LOCALE_BY_COUNTRY.get(country, "en_US"))
    profile_fake.seed_instance(42 * 10_000 + creator_id)
    handle = _unique_handle(profile_fake, rng, used_handles)
    name = profile_fake.name()
    brand_pool = [brand for niche in [primary_niche, *secondary] for brand in BRANDS.get(niche, [])]
    if not brand_pool:
        brand_pool = [f"{primary_niche} Collective", f"{primary_niche} Studio"]
    collaborations = rng.sample(brand_pool, k=min(len(brand_pool), rng.randint(0, 3)))
    audience_country = country if rng.random() < 0.65 else CITY_COUNTRY[rng.choice(cities)]

    return Influencer(
        id=creator_id,
        name=name,
        handle=handle,
        niche=primary_niche,
        secondary_niches=secondary,
        platform=platform,
        city=city,
        country=country,
        language=rng.choice(LANGUAGES_BY_COUNTRY.get(country, ["English"])),
        followers=followers,
        engagement=engagement,
        average_views=views,
        average_likes=likes,
        average_comments=comments,
        verified=followers >= 500_000 and rng.random() < 0.4,
        posts_per_week=rng.randint(2, 14),
        account_age_years=rng.randint(1, 12),
        content_style=rng.choice(CONTENT_STYLES),
        audience_age=rng.choice(["13-17", "18-24", "25-34", "35-44"]),
        audience_gender=rng.choice(["60% Female", "55% Female", "55% Male", "62% Male"]),
        audience_country=audience_country,
        brand_collaborations=collaborations,
        tags=tags,
        bio=f"{name}. {rng.choice(BIOS).format(topics=', '.join([primary_niche, *secondary]))} Based in {city}, {country}.",
    )
