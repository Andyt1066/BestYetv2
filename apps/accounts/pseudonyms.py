"""Stable, regenerable pseudonyms shown on boards and notices to non-friends."""

import secrets

ADJECTIVES = [
    "amber",
    "bold",
    "brisk",
    "bronze",
    "calm",
    "cobalt",
    "copper",
    "crimson",
    "deft",
    "eager",
    "ember",
    "fleet",
    "granite",
    "hardy",
    "iron",
    "ivory",
    "jade",
    "keen",
    "lively",
    "lunar",
    "mighty",
    "nimble",
    "onyx",
    "peppy",
    "quick",
    "rapid",
    "rugged",
    "scarlet",
    "silver",
    "solid",
    "steady",
    "steel",
    "stone",
    "sturdy",
    "swift",
    "titan",
    "tough",
    "vivid",
    "wired",
    "zesty",
]

NOUNS = [
    "badger",
    "bear",
    "bison",
    "boar",
    "bull",
    "condor",
    "cougar",
    "crane",
    "eagle",
    "elk",
    "falcon",
    "fox",
    "gorilla",
    "hawk",
    "heron",
    "hound",
    "ibex",
    "jaguar",
    "kestrel",
    "lion",
    "lynx",
    "mammoth",
    "marten",
    "moose",
    "orca",
    "otter",
    "owl",
    "ox",
    "panther",
    "puma",
    "ram",
    "raven",
    "rhino",
    "stag",
    "tiger",
    "walrus",
    "wolf",
    "wolverine",
    "wombat",
    "yak",
]


def generate_candidate():
    adjective = secrets.choice(ADJECTIVES)
    noun = secrets.choice(NOUNS)
    number = secrets.randbelow(90) + 10
    return f"{adjective}-{noun}-{number}"


def generate_unique(taken_queryset_fn):
    """Return a candidate not currently taken; caller supplies an exists-check."""
    while True:
        candidate = generate_candidate()
        if not taken_queryset_fn(candidate):
            return candidate
