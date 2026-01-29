TOPIC_RESOURCES = {
    "python": [
        "https://docs.python.org/3/",
        "https://realpython.com/",
    ],
    "asyncio": [
        "https://docs.python.org/3/library/asyncio.html",
        "https://superfastpython.com/python-asyncio/",
    ],
    "algorithms": [
        "https://cp-algorithms.com/",
        "https://neetcode.io/roadmap",
    ],
    "databases": [
        "https://www.postgresql.org/docs/",
        "https://use-the-index-luke.com/",
    ],
}


def get_resources(topic: str) -> list[str]:
    topic_l = topic.lower()
    for key, links in TOPIC_RESOURCES.items():
        if key in topic_l:
            return links
    return ["https://developer.mozilla.org/", "https://docs.python.org/3/"]

