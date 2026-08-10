"""Tamil Nadu: scrape the RTI portal, rebuild the tree offline, screen for relevance.

See README.md in this directory for the two site quirks that shape the crawler:
the portal is geo-fenced to India, and its sub-office links carry a token that is
randomised on every request, so identity has to be content-based.
"""
