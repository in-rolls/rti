"""Per-state scrapers that build the universe of filable public authorities.

Each state package follows the same three stages: scrape the portal to raw HTML,
parse it offline into a node tree, then screen the offices for relevance. Their
output feeds `rti.frame`, which merges every state's universe into one frame.
"""
