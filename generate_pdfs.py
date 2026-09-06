#!/usr/bin/env python3
"""Generate 100 synthetic character-lore PDFs for testing Estuary batch character creation.

Usage:
    python generate_pdfs.py <out_dir> <base_url>

73 characters share the 100 PDFs:

    58 characters x 1 PDF  (a complete dossier)
    10 characters x 2 PDFs (dossier + relationships)
     4 characters x 3 PDFs (dossier + relationships + one chronicle volume)
     1 character  x 10 PDFs (dossier + relationships + eight chronicle volumes; the per-item cap)

Each volume of a multi-PDF character carries facts that appear ONLY in that volume
(dossier: lucky number, favourite dish, pet; relationships: workshop password, rival,
mentor, friend; chronicle volume k: what the character calls one possession), so a
document that failed to ingest or link is detectable by asking the character.

Writes <out_dir>/pdfs/*.pdf, manifest.json, urls.txt, batch_request.json (all 73 items,
exactly 100 documents), batch_request_10.json (first 10 items: singles plus the 2-, 3-
and 10-document cases) and batch_request_multi.json (only the 15 multi-PDF characters).
Deterministic: the same seed always reproduces the same documents.
All content is fictional and machine-generated.
"""
import json
import os
import random
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    import pymupdf  # only used to verify what was written
except ImportError:  # pragma: no cover
    pymupdf = None

SEED = 20260905
CHAR_COUNT = 73
PDF_COUNT = 100

# character index -> number of PDFs. Indexes 1..4 are fixed so batch_request_10.json
# always contains a 1-, 2-, 3- and 10-document item; the remaining multi-PDF
# characters are spread over the rest of the list.
FIXED_DOC_COUNTS = {1: 1, 2: 2, 3: 3, 4: 10}
EXTRA_DOUBLES = 9
EXTRA_TRIPLES = 3

FIRST_NAMES = [
    "Torvald", "Mara", "Ysolde", "Bram", "Kestrel", "Oduya", "Fenwick", "Liora", "Hamish", "Zeph",
    "Ingrid", "Cassius", "Nkechi", "Rowan", "Sable", "Thaddeus", "Wren", "Osric", "Petra", "Quillon",
    "Ravi", "Seraphine", "Tomasz", "Ulla", "Viggo", "Wilhelmina", "Xiomara", "Yusuf", "Zora", "Anouk",
    "Baptiste", "Calloway", "Delphine", "Eamon", "Farida", "Gideon", "Halcyon", "Imogen", "Jorah", "Kwame",
    "Leocadia", "Matthias", "Nadira", "Orsolya", "Percival", "Qadira", "Rhoswen", "Soren", "Tallulah", "Umberto",
    "Vesna", "Wendeline", "Xavier", "Yevgenia", "Zubair", "Astrid", "Benedikt", "Corvina", "Dashiell", "Elowen",
    "Fitzgerald", "Greta", "Hollis", "Isadora", "Jasper", "Katarina", "Lysander", "Marisol", "Nikolai", "Octavia",
    "Pilar", "Quentin", "Rosalind", "Sixten", "Tiberius", "Ursula", "Valentin", "Winifred", "Xanthe", "Yannick",
    "Zelda", "Amadou", "Brigid", "Caspian", "Dorothea", "Emeric", "Freya", "Gustav", "Hyacinth", "Ignatius",
    "Juniper", "Kenji", "Lucienne", "Magnus", "Noor", "Olwen", "Phaedra", "Rurik", "Sunniva", "Teodora",
]
assert len(set(FIRST_NAMES)) == len(FIRST_NAMES) >= CHAR_COUNT

SURNAMES = [
    "Ashgrove", "Blackwater", "Corvane", "Duskmere", "Ellery", "Fairweather", "Grimsby", "Hollowell",
    "Irongate", "Jessop", "Kaldwin", "Larkspur", "Merriwether", "Nightingale", "Oakhurst", "Penhallow",
    "Quenneville", "Ravensworth", "Stillwater", "Thornbury", "Underhill", "Vasquez-Moor", "Whitlock",
    "Yarrow", "Zimmerling", "Achterberg", "Brightmoor", "Castellan", "Dunmore", "Everhart", "Falkenrath",
    "Greywind", "Hartwell", "Ironside", "Kettleburn", "Lindqvist", "Marchetti", "Norwood", "Okonkwo", "Pemberton",
]

SETTINGS = [
    {"name": "the harbor town of Saltmarsh", "locations": ["the Old Quay", "Gull Street market", "the Tidewatch lighthouse", "the Brine and Bell tavern", "the drydocks"], "currency": "silver marks", "faction": "the Harbormasters' Guild"},
    {"name": "Kepler Station, a mining outpost orbiting the gas giant Oryn", "locations": ["Ring Deck 4", "the hydroponics bay", "the ore refinery", "Dockmaster's Row", "the observation lounge"], "currency": "station credits", "faction": "the Oryn Extraction Consortium"},
    {"name": "Neon Meridian, a rain-soaked megacity", "locations": ["the Undermarket", "Sector 9 transit hub", "the Glass District", "Kowloon Arcade", "the flooded lower rings"], "currency": "meridian scrip", "faction": "the Halcyon Syndicate"},
    {"name": "the Academy of Vell", "locations": ["the Hall of Echoes", "the north observatory", "the greenhouse cloisters", "the bell tower", "the candle library"], "currency": "guilders", "faction": "the Faculty of Applied Wonders"},
    {"name": "the Dust Road caravan routes", "locations": ["Wayrest Springs", "the Salt Flats", "Three Crows junction", "the Cracked Cistern", "Emberfall Pass"], "currency": "trade tokens", "faction": "the Caravaners' Compact"},
    {"name": "the Emerald Court of Ardenne", "locations": ["the Mirror Gallery", "the royal mews", "the lower kitchens", "the Sunken Garden", "the Chancery"], "currency": "crowns", "faction": "House Ardenne"},
    {"name": "Lumen Falls, a small mountain town in 1987", "locations": ["the Falls Diner", "Route 12 gas station", "the shuttered paper mill", "Pinecrest High", "the community radio shack"], "currency": "dollars", "faction": "the Lumen Falls town council"},
    {"name": "the Drowned Library beneath Old Cassilon", "locations": ["the Reading Well", "the Stacks of Ash", "the cataloguers' gallery", "the sluice gates", "the Archivist's cell"], "currency": "ink-weights", "faction": "the Order of Wet Pages"},
    {"name": "Verdance, a floating garden city", "locations": ["the Canopy Walk", "the root-cellar markets", "Terrace Twelve", "the pollinators' hall", "the tether docks"], "currency": "seed-notes", "faction": "the Verdance Stewardship"},
    {"name": "the Frostwall garrison on the northern border", "locations": ["the east rampart", "the quartermaster's stores", "the signal tower", "the frozen moat", "the mess hall"], "currency": "iron pennies", "faction": "the Frostwall Legion"},
    {"name": "Bellwether Farms, an agricultural cooperative on Mars", "locations": ["Dome C", "the water reclaimer", "the seed vault", "the rover garage", "the commons"], "currency": "co-op shares", "faction": "the Bellwether Cooperative"},
    {"name": "the traveling Circus of Marrow and Light", "locations": ["the big top", "the menagerie wagons", "the costume tent", "the cookfire", "the ticket wagon"], "currency": "copper bits", "faction": "the Ringmaster's troupe"},
]

ROLES = [
    "blacksmith", "innkeeper", "cartographer", "herbalist", "lighthouse keeper", "dockmaster", "archivist",
    "courier", "bounty hunter", "ship's engineer", "hydroponics technician", "street medic", "noodle-stall cook",
    "tattooist", "retired duelist", "court astronomer", "spymaster", "gardener", "glassblower", "beekeeper",
    "radio operator", "tram conductor", "tutor", "fortune teller", "acrobat", "ring announcer", "quartermaster",
    "scout", "alchemist", "bookbinder", "clockmaker", "pearl diver", "fishmonger", "stable hand", "exorcist",
    "tax collector", "playwright", "chandler", "translator", "salvage pilot",
]

TRAITS = [
    "gruff but generous", "cheerfully pessimistic", "meticulous and easily flustered", "warm, nosy and impossible to offend",
    "quietly ambitious", "loyal to a fault", "sardonic with a soft center", "restless and curious", "patient as stone",
    "theatrical and vain", "anxious but brave when it counts", "blunt, practical and allergic to small talk",
    "dreamy and forgetful", "fiercely protective of newcomers", "competitive about everything", "gentle and slow to trust",
    "proud of a craft nobody appreciates", "superstitious and observant", "playful, with a cruel streak they regret",
    "stubborn, principled and tired", "charming and evasive", "kind in deeds, sharp in words", "melancholy but funny",
    "methodical and secretly sentimental", "boisterous, generous, easily bored", "cautious, precise and haunted",
    "sunny and relentlessly optimistic", "cynical mentor who wants to be proven wrong", "shy, brilliant and defensive",
    "hot-tempered, quick to forgive",
]

SPEECH = [
    "speaks in short, clipped sentences and dislikes being rushed", "never uses contractions and apologises for it",
    "peppers everything with nautical metaphors", "answers a question with a question before giving a real answer",
    "hums a few notes between thoughts", "uses trade jargon and then patiently explains it",
    "addresses everyone as 'friend' until they earn a name", "speaks softly and expects people to lean in",
    "quotes half-remembered proverbs, often wrongly", "counts things aloud when nervous",
    "tells long stories that circle back to the point eventually", "refuses to say the word 'no' outright",
    "laughs at their own jokes a beat too early", "switches to formal speech when angry",
    "narrates their own actions under their breath", "ends sentences with 'you understand?'",
    "gives directions by landmark, never by street name", "compliments people before disagreeing with them",
    "mutters prices and measurements while thinking", "swears by the weather instead of the gods",
]

DISHES = [
    "eel pie", "barley stew", "saffron rice", "pickled plums", "smoked trout", "mushroom dumplings", "honey cakes",
    "black garlic noodles", "goat cheese tart", "lentil fritters", "cardamom buns", "fig and walnut bread",
    "roast root vegetables", "crab bisque", "lamb skewers", "sour cherry soup", "seaweed crackers", "peppered venison",
    "coconut porridge", "tamarind chicken", "fried plantains", "blue corn flatbread", "juniper sausages",
    "apple and onion hash", "miso eggplant", "spiced pumpkin dumplings", "cold buckwheat noodles", "clam fritters",
    "rosewater pudding", "chestnut soup", "ginger duck", "salt-baked potatoes", "green tomato chutney", "oat and ale bread",
    "peach hand pies", "wild rice pilaf", "smoked pepper hummus", "pear and blue cheese salad", "molasses beans",
    "sesame brittle",
]
DISH_PREPS = ["grandmother's", "the tavern's", "midnight", "festival", "hand-rolled", "charred", "twice-cooked", "cold"]

PET_SPECIES = ["cat", "raven", "hound", "goat", "tortoise", "ferret", "parrot", "hedgehog", "owl", "salamander",
               "lizard", "rabbit", "pigeon", "fox", "crow", "gecko", "mouse", "hawk", "toad", "beetle"]
PET_NAMES = ["Biscuit", "Admiral", "Pockets", "Marigold", "Thimble", "Grumble", "Sprocket", "Dumpling", "Ledger",
             "Pebble", "Tuesday", "Cinder", "Bramble", "Nutmeg", "Waffles", "Captain", "Sorrow", "Pip", "Rook",
             "Clementine", "Fidget", "Barnaby", "Turnip", "Halo", "Mortimer", "Saucer", "Vesper", "Comet", "Ollie",
             "Marzipan", "Quibble", "Radish", "Tinker", "Umbra", "Velvet", "Whistle", "Yolk", "Ziggy", "Amos", "Bellows"]

PASS_WORDS = ["amber", "lantern", "velvet", "harbor", "quill", "ember", "marble", "thistle", "copper", "meadow", "orchid",
              "saffron", "cobalt", "willow", "granite", "sparrow", "indigo", "tide", "cinder", "hollow", "juniper",
              "lattice", "mirror", "nutmeg", "obsidian", "pepper", "quartz", "raven", "tallow", "umber", "vellum",
              "walnut", "yarrow", "zephyr", "anvil", "birch", "cedar", "dune", "fern", "gale", "heron", "iris", "jade",
              "kelp", "linen", "moss", "north", "oak", "plume", "reed", "slate", "thorn", "vane", "wick", "ash", "brine",
              "cove", "drift", "ewe", "fable"]

# Names a character gives to a possession; one per chronicle volume, unique within a character.
POSSESSION_NAMES = ["Old Patience", "The Widow", "Second Chance", "Grandmother's Grudge", "Little Thunder", "Mercy",
                    "The Argument", "Halfpenny", "Long Tuesday", "Saint Nobody", "The Understudy", "Quiet Hours",
                    "Borrowed Time", "The Apology", "Wet Matches", "North Wind", "Sullen Kate", "The Debt", "Sparrowhawk",
                    "Last Word", "Pale Morning", "The Alibi", "Housekeeping", "Fair Warning", "Old Harbor", "Small Hours",
                    "Thin Ice", "The Verdict", "Honest Work", "Lost Cause"]

HOMETOWNS = ["Greywater", "Little Ashby", "Port Calloway", "the Mirefold", "Hessen Cross", "Two Rivers", "Bittermoor",
             "Kingsreach", "Solace", "the Ninth Terrace", "Oldbridge", "Wickham Hollow", "Marrow's End", "Sunder",
             "Halvard", "the Copper Coast", "Fennick", "Dry Harbor", "Elmsworth", "Tallow Bay", "Caldera Row",
             "New Aster", "Redgate", "the Lantern Quarter", "Whitmoor", "Verity Falls", "Stonebridge", "Anselm",
             "the Weeping Shoals", "Kettering"]

SECRETS = [
    "{name} once forged a letter of passage for a stranger who turned out to be a wanted person, and still keeps the copy.",
    "{name} cannot actually read the old script everyone assumes they can, and has memorised the important pages.",
    "{name} owes {rival} a debt of {n} {currency} that neither of them mentions.",
    "{name} secretly funds an orphanage in {hometown} and would be mortified if anyone found out.",
    "{name} was the one who let the animals loose during the festival three years ago.",
    "{name} has a sibling nobody in {setting} knows about, living quietly in {hometown}.",
    "{name} keeps a list of everyone who has ever been kind to them, and repays each one eventually.",
    "{name} is terrified of deep water and hides it with jokes.",
    "{name} sold a family heirloom to pay for {friend}'s medicine and told everyone it was stolen.",
    "{name} writes poetry under the pen name 'The {password_word}' and has a small, devoted readership.",
    "{name} once turned down an offer from {faction} that would have made them rich, and wonders about it nightly.",
    "{name} has never told {mentor} that the famous 'accident' was deliberate.",
]

GOALS = ["to reopen the shop their parents lost", "to map every path through {loc}", "to find out what happened to the missing caravan",
         "to be trusted by {faction} again", "to retire somewhere warm", "to win the harvest fair for the fifth time",
         "to teach one apprentice who actually listens", "to pay off the last of the debt by winter", "to see the ocean once",
         "to prove the old tunnels are real", "to keep out of trouble for one full season",
         "to finish the great ledger of {setting}", "to be forgotten by the people who remember the fire",
         "to earn the title of master before turning fifty", "to build a boat with no nails in it"]

FEARS = ["fire in enclosed spaces", "being forgotten", "the bells at midnight", "letting people down", "open water",
         "crowds that go quiet all at once", "owing anything to {faction}", "losing their sense of smell", "the far side of {loc}",
         "being seen to cry", "a knock at the door after dark", "birds indoors", "running out of salt", "mirrors in the dark"]

EVENT_TEMPLATES = [
    "{name} repaired the {thing} at {loc} for {other}, who paid in {n} {currency} and a long story about {topic}.",
    "A dispute over {topic} flared up between {name} and a neighbour outside {loc}; it ended, as usual, with neither of them conceding.",
    "{name} found a {thing} half-buried near {loc} and spent the evening trying to work out who had lost it.",
    "{faction} sent a notice about {topic}. {name} read it twice, folded it into a square and used it to level a table.",
    "{other} came by asking about {topic}. {name} said nothing useful and made tea instead.",
    "The weather turned. {name} moved the {thing} indoors and wrote three lines to an old friend about {topic}.",
    "{name} was hired to carry a {thing} from {loc} to {loc2} without opening it, and mostly succeeded.",
    "At {loc}, {name} taught a newcomer how to tell a real {thing} from a fake one by weight alone.",
    "Rumours about {topic} reached {loc}. {name} pretended not to care and then asked everyone about it.",
    "{name} won {n} {currency} on a bet about {topic} and spent all of it on supper.",
    "A stranger asked {name} for the password to the workshop. {name} laughed and said it was written on the wall, which it is not.",
    "{name} spent the day counting stock at {loc}: {n} of everything, except the {thing}, which is always short.",
    "An old teacher visited unannounced. They argued about {topic} for an hour and parted better friends than before.",
    "{name} closed early, walked to {loc2}, and watched the lights come on.",
    "Someone left a {thing} on the doorstep with no note. {name} has a suspect and is probably right.",
]
THINGS = ["brass lantern", "cracked compass", "iron kettle", "ledger", "coil of rope", "sextant", "wax seal", "clockwork bird",
          "sack of salt", "bolt of linen", "signal flag", "copper pipe", "tin whistle", "grain scale", "spool of wire",
          "glass float", "hand bell", "bundle of letters", "oilskin map", "pair of spectacles"]
TOPICS = ["the tariff on salt", "the new curfew", "whether the bridge will hold", "the price of lamp oil", "the missing shipment",
          "who really won the regatta", "the rumour of a second well", "the old tunnels", "the harvest count", "the census",
          "the right way to mend a net", "the comet", "the quarantine", "the singing at the docks", "the tax on doors"]
SEASONS = ["spring", "summer", "autumn", "winter"]

# Chinese and Japanese fixed-template sections for a handful of documents.
CJK_ZH = "{name}是{setting_en}的一名{role_en}。{name}的幸运数字是{lucky}。{name}最喜欢的菜是{dish}。{name}养了一只叫{pet_name}的{species_en}。"
CJK_ZH_PW = "进入工坊的口令是「{password}」。"
CJK_JA = "{name}は{setting_en}の{role_en}です。{name}のラッキーナンバーは{lucky}です。好きな料理は{dish}です。{pet_name}という名前の{species_en}を飼っています。"
CJK_JA_PW = "工房の合言葉は「{password}」です。"

VOLUME_TITLES = {"single": "Character Dossier", "dossier": "Character Dossier", "relationships": "Relationships and Secrets"}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cap(s: str) -> str:
    return s[0].upper() + s[1:]


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def assign_doc_counts(rng: random.Random):
    counts = dict(FIXED_DOC_COUNTS)
    rest = [i for i in range(1, CHAR_COUNT + 1) if i not in counts]
    picks = rng.sample(rest, EXTRA_DOUBLES + EXTRA_TRIPLES)
    for i in picks[:EXTRA_DOUBLES]:
        counts[i] = 2
    for i in picks[EXTRA_DOUBLES:]:
        counts[i] = 3
    out = [counts.get(i, 1) for i in range(1, CHAR_COUNT + 1)]
    assert sum(out) == PDF_COUNT, sum(out)
    return out


def kinds_for(n_docs: int):
    if n_docs == 1:
        return ["single"]
    return ["dossier", "relationships"] + ["chronicle"] * (n_docs - 2)


def make_characters(rng: random.Random, doc_counts):
    surnames = [rng.choice(SURNAMES) for _ in range(CHAR_COUNT)]
    dishes = rng.sample([f"{p} {d}" for p in DISH_PREPS for d in DISHES], CHAR_COUNT)
    pets = rng.sample([(n, s) for n in PET_NAMES for s in PET_SPECIES], CHAR_COUNT)
    lucky = rng.sample(range(100, 1000), CHAR_COUNT)
    passwords = rng.sample([f"{a}-{b}" for a in PASS_WORDS for b in PASS_WORDS if a != b], CHAR_COUNT)
    chars = []
    for i in range(CHAR_COUNT):
        setting = SETTINGS[i % len(SETTINGS)] if i < len(SETTINGS) else rng.choice(SETTINGS)
        first = FIRST_NAMES[i]
        n_chron = max(0, doc_counts[i] - 2)
        chars.append({
            "index": i + 1,
            "first_name": first,
            "name": f"{first} {surnames[i]}",
            "role": rng.choice(ROLES),
            "setting": setting["name"],
            "_setting": setting,
            "traits": rng.choice(TRAITS),
            "speech": rng.choice(SPEECH),
            "age": rng.randint(19, 78),
            "hometown": rng.choice(HOMETOWNS),
            "favorite_dish": dishes[i],
            "pet_name": pets[i][0],
            "pet_species": pets[i][1],
            "lucky_number": lucky[i],
            "password": passwords[i],
            "goal_t": rng.choice(GOALS),
            "fear_t": rng.choice(FEARS),
            "secret_t": rng.choice(SECRETS),
            "doc_count": doc_counts[i],
            "kinds": kinds_for(doc_counts[i]),
            # one (thing, name) pair per chronicle volume, unique within the character
            "possessions": list(zip(rng.sample(THINGS, n_chron), rng.sample(POSSESSION_NAMES, n_chron))),
        })
    # Cross-links so the corpus has relationships to ask about.
    for i, ch in enumerate(chars):
        ch["mentor"] = chars[(i - 7) % CHAR_COUNT]["name"]
        ch["rival"] = chars[(i + 13) % CHAR_COUNT]["name"]
        ch["friend"] = chars[(i + 41) % CHAR_COUNT]["name"]
    for ch in chars:
        s = ch["_setting"]
        fmt = dict(
            name=ch["first_name"], rival=ch["rival"], friend=ch["friend"], mentor=ch["mentor"],
            hometown=ch["hometown"], setting=ch["setting"], faction=s["faction"], currency=s["currency"],
            loc=s["locations"][0], n=ch["lucky_number"] // 3, password_word=ch["password"].split("-")[0].title(),
        )
        ch["goal"] = ch.pop("goal_t").format(**fmt)
        ch["fear"] = ch.pop("fear_t").format(**fmt)
        ch["secret"] = ch.pop("secret_t").format(**fmt)
        ch["tagline"] = f"{cap(ch['traits'])} {ch['role']} of {ch['setting']}"
    return chars


def page_targets(rng: random.Random, n: int):
    """Padding targets for the documents that carry a chronicle (singles and chronicle volumes)."""
    targets = ([rng.randint(1, 3) for _ in range(40)] + [rng.randint(4, 8) for _ in range(20)]
               + [rng.randint(10, 25) for _ in range(7)] + [rng.randint(40, 60) for _ in range(3)])
    rng.shuffle(targets)
    assert len(targets) >= n, (len(targets), n)
    return targets[:n]


def chronicle(ch, n_entries, rng: random.Random, possession=None):
    s = ch["_setting"]
    out = []
    year = rng.randint(3, 40)
    for k in range(n_entries):
        if k % 4 == 0:
            year += rng.randint(0, 1)
        locs = rng.sample(s["locations"], 2)
        sentences = []
        for _ in range(rng.randint(3, 5)):
            t = rng.choice(EVENT_TEMPLATES)
            sentences.append(t.format(
                name=ch["first_name"], other=rng.choice(FIRST_NAMES), loc=locs[0], loc2=locs[1],
                faction=s["faction"], currency=s["currency"], n=rng.randint(2, 90),
                thing=rng.choice(THINGS), topic=rng.choice(TOPICS),
            ))
        if possession and k == 0:
            thing, pname = possession
            sentences.append(f"{ch['first_name']} polished '{pname}', the {thing}, and said nothing about it.")
        out.append((f"Entry {k + 1}, {rng.choice(SEASONS)} of year {year}", " ".join(sentences)))
    return out


def facts_table(rows, styles):
    tbl = Table([[Paragraph(esc(a), styles["small"]), Paragraph(esc(b), styles["body"])] for a, b in rows],
                colWidths=[1.6 * inch, 4.6 * inch])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def build_doc(path, ch, kind, vol_no, chron_no, target_pages, cjk, rng: random.Random, styles):
    """Write one PDF. kind: single | dossier | relationships | chronicle."""
    s = ch["_setting"]
    first = ch["first_name"]
    n_vols = ch["doc_count"]
    title = VOLUME_TITLES.get(kind) or f"Chronicle, volume {chron_no}"
    doc = SimpleDocTemplate(
        path, pagesize=LETTER, leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
        title=f"{ch['name']}: {title}", author="Estuary synthetic test fixtures",
        subject=f"Lore for {ch['name']}, {ch['role']} of {ch['setting']}",
    )
    H1, H2, BODY, SMALL, TITLE = (styles[k] for k in ("h1", "h2", "body", "small", "title"))

    def P(t, st=BODY):
        return Paragraph(esc(t), st)

    story = [Paragraph(esc(ch["name"]), TITLE), Paragraph(esc(title), H2), Spacer(1, 6), P(ch["tagline"], SMALL)]
    if n_vols > 1:
        story.append(P(f"Volume {vol_no} of {n_vols} in the {first} {ch['name'].split()[-1]} collection. "
                       f"The other volumes cover the rest of this character's record.", SMALL))
    story.append(Spacer(1, 18))

    if kind in ("single", "dossier"):
        story += [
            Paragraph("Overview", H1),
            P(f"{ch['name']} is a {ch['role']} living in {ch['setting']}. {first} is {ch['age']} years old, "
              f"originally from {ch['hometown']}, and is known around {s['locations'][0]} as {ch['traits']}. "
              f"In conversation {first} {ch['speech']}."),
            Spacer(1, 10),
            Paragraph("Background", H1),
            P(f"{first} arrived in {ch['setting']} {rng.randint(2, 30)} years ago after leaving {ch['hometown']} "
              f"under circumstances {first} describes differently every time. The first job was hauling for "
              f"{s['faction']}; the second was the one that stuck. Today {first} works as a {ch['role']} near "
              f"{s['locations'][1]} and is paid, when paid at all, in {s['currency']}."),
            Spacer(1, 6),
        ]
        if kind == "single":
            story += [P(f"{first} learned the trade from {ch['mentor']}, who still drops by unannounced. "
                        f"The longest-running feud in {first}'s life is with {ch['rival']}, over a matter neither will explain. "
                        f"The person {first} trusts most is {ch['friend']}."), Spacer(1, 6)]
        else:
            story += [P(f"The people in {first}'s life, and the things {first} would rather nobody knew, are recorded "
                        f"in the Relationships and Secrets volume of this collection."), Spacer(1, 6)]
        story += [
            P(f"Current goal: {ch['goal']}. Greatest fear: {ch['fear']}."),
            Spacer(1, 10),
            Paragraph("Personality and speech", H1),
            P(f"Temperament: {ch['traits']}."),
            P(f"Speech pattern: {first} {ch['speech']}."),
            P(f"Tells: when lying, {first} mentions {ch['pet_name']} the {ch['pet_species']} for no reason."),
            Spacer(1, 10),
            Paragraph("Verified facts", H1),
            P("These facts are canonical for this character and may be used to verify knowledge-bank retrieval.", SMALL),
            Spacer(1, 4),
        ]
        rows = [["Full name", ch["name"]], ["Role", ch["role"]], ["Home", ch["setting"]], ["Hometown", ch["hometown"]],
                ["Age", str(ch["age"])], ["Favourite dish", ch["favorite_dish"]],
                ["Pet", f"{ch['pet_name']}, a {ch['pet_species']}"], ["Lucky number", str(ch["lucky_number"])]]
        if kind == "single":
            rows += [["Workshop password", ch["password"]], ["Mentor", ch["mentor"]], ["Rival", ch["rival"]],
                     ["Closest friend", ch["friend"]]]
        story += [facts_table(rows, styles), Spacer(1, 10)]
        if kind == "single":
            story += [Paragraph("Secret", H1), P(ch["secret"]), Spacer(1, 10)]
        story += [
            Paragraph("Sample dialogue", H1),
            P("Visitor: What do you do here?"),
            P(f"{first}: I am the {ch['role']}. Has been that way longer than you have been asking questions."),
            P("Visitor: What is your favourite thing to eat?"),
            P(f"{first}: {cap(ch['favorite_dish'])}. " + (f"Do not tell {ch['rival'].split()[0]} I said so."
                                                        if kind == "single" else "Do not tell anyone I said so.")),
            P(f"Visitor: Is {ch['pet_name']} yours?"),
            P(f"{first}: {ch['pet_name']} belongs to nobody. {ch['pet_name']} tolerates me. "
              f"Lucky number is {ch['lucky_number']}, if you were about to ask."),
        ]
        if cjk:
            fmt = dict(name=first, setting_en=ch["setting"], role_en=ch["role"], lucky=ch["lucky_number"],
                       dish=ch["favorite_dish"], pet_name=ch["pet_name"], species_en=ch["pet_species"], password=ch["password"])
            zh = CJK_ZH.format(**fmt) + (CJK_ZH_PW.format(**fmt) if kind == "single" else "")
            ja = CJK_JA.format(**fmt) + (CJK_JA_PW.format(**fmt) if kind == "single" else "")
            story += [Spacer(1, 10), Paragraph("Summary (Chinese)", H1), Paragraph(esc(zh), styles["zh"]),
                      Spacer(1, 6), Paragraph("Summary (Japanese)", H1), Paragraph(esc(ja), styles["ja"])]

    elif kind == "relationships":
        story += [
            Paragraph("The people in this life", H1),
            P(f"{first} learned the trade from {ch['mentor']}, who still drops by unannounced and still finds fault "
              f"with the way {first} holds a tool. The longest-running feud in {first}'s life is with {ch['rival']}, "
              f"over a matter neither will explain; they are civil in public and merciless in private. "
              f"The person {first} trusts most is {ch['friend']}, who has never once asked for anything."),
            Spacer(1, 10),
            Paragraph("Verified relationships", H1),
            P("These facts are canonical for this character and may be used to verify knowledge-bank retrieval.", SMALL),
            Spacer(1, 4),
            facts_table([["Full name", ch["name"]], ["Mentor", ch["mentor"]], ["Rival", ch["rival"]],
                         ["Closest friend", ch["friend"]], ["Workshop password", ch["password"]]], styles),
            Spacer(1, 10),
            Paragraph("Secret", H1), P(ch["secret"]), Spacer(1, 10),
            Paragraph("The workshop password", H1),
            P(f"The door to {first}'s workshop near {s['locations'][1]} answers to the password '{ch['password']}'. "
              f"{first} has never changed it and tells exactly one person per year, usually by accident. "
              f"{ch['friend'].split()[0]} knows it. {ch['rival'].split()[0]} pretends not to."),
            Spacer(1, 10),
            Paragraph("Sample dialogue", H1),
            P("Visitor: Who taught you?"),
            P(f"{first}: {ch['mentor']}. Do not repeat that where {ch['mentor'].split()[0]} can hear it; the head is large enough."),
            P(f"Visitor: And {ch['rival'].split()[0]}?"),
            P(f"{first}: {ch['rival']} is a rival. That is the polite word. We have others."),
            P("Visitor: What is the password to the workshop?"),
            P(f"{first}: You are the second person to ask this week. Fine. It is '{ch['password']}'. Say it once and forget it."),
        ]

    else:  # chronicle
        thing, pname = ch["possessions"][chron_no - 1]
        story += [
            Paragraph("About this volume", H1),
            P(f"Day-to-day records kept by {first}, {ch['role']} of {ch['setting']}, in no particular order of importance. "
              f"Among the things {first} keeps at {s['locations'][0]} is a {thing}; {first} calls it '{pname}' "
              f"and will not explain why. It appears in these pages more often than it deserves."),
            Spacer(1, 6),
            facts_table([["Full name", ch["name"]], ["Volume", f"Chronicle {chron_no}"],
                         [f"Name of the {thing}", pname]], styles),
            Spacer(1, 10),
        ]

    if kind in ("single", "chronicle"):
        n_entries = int(max(0, target_pages - 1.6) * 8.5) if kind == "single" else max(3, int((target_pages - 0.6) * 8.5))
        possession = ch["possessions"][chron_no - 1] if kind == "chronicle" else None
        if n_entries:
            if kind == "single":
                story += [PageBreak(), Paragraph("Chronicle", H1),
                          P("Day-to-day records kept by the character, in no particular order of importance.", SMALL), Spacer(1, 6)]
            else:
                story += [Paragraph("Entries", H1)]
            for head, body in chronicle(ch, n_entries, rng, possession):
                story += [Paragraph(esc(head), H2), P(body), Spacer(1, 5)]
    doc.build(story)


def make_styles():
    ss = getSampleStyleSheet()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    return {
        "title": ParagraphStyle("title", parent=ss["Title"], fontSize=24, leading=28, alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=ss["Heading2"], fontSize=13, leading=16, spaceBefore=4),
        "h2": ParagraphStyle("h2", parent=ss["Heading4"], fontSize=10.5, leading=13, textColor=colors.HexColor("#333333")),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=13.5),
        "small": ParagraphStyle("small", parent=ss["BodyText"], fontName="Helvetica-Oblique", fontSize=9, leading=12,
                                textColor=colors.HexColor("#555555")),
        "zh": ParagraphStyle("zh", fontName="STSong-Light", fontSize=10.5, leading=15),
        "ja": ParagraphStyle("ja", fontName="HeiseiMin-W3", fontSize=10.5, leading=15),
    }


def verify(path, ch, kind, chron_no):
    """Check the facts that belong to this volume are extractable, and the password stays out of other volumes."""
    if pymupdf is None:
        return None
    with pymupdf.open(path) as d:
        pages = d.page_count
        text = " ".join(p.get_text() for p in d)
    need = {
        "single": [ch["name"], ch["password"], ch["lucky_number"], ch["favorite_dish"], ch["pet_name"], ch["rival"]],
        "dossier": [ch["name"], ch["lucky_number"], ch["favorite_dish"], ch["pet_name"]],
        "relationships": [ch["name"], ch["password"], ch["rival"], ch["mentor"], ch["friend"]],
        "chronicle": [ch["name"]] + ([ch["possessions"][chron_no - 1][1]] if kind == "chronicle" else []),
    }[kind]
    ok = all(str(v) in text for v in need)
    if kind in ("dossier", "chronicle"):
        ok = ok and ch["password"] not in text
    return {"pages": pages, "facts_extractable": ok}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out_dir, base_url = sys.argv[1], sys.argv[2].rstrip("/")
    pdf_dir = os.path.join(out_dir, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    for old in os.listdir(pdf_dir):
        os.remove(os.path.join(pdf_dir, old))
    rng = random.Random(SEED)
    doc_counts = assign_doc_counts(rng)
    chars = make_characters(rng, doc_counts)
    n_padded = sum(1 for ch in chars for k in ch["kinds"] if k in ("single", "chronicle"))
    targets = iter(page_targets(rng, n_padded))
    styles = make_styles()
    characters_out, documents_out, items = [], [], []
    for ch in chars:
        first = ch["first_name"]
        slug = slugify(ch["name"])
        custom_id = f"test-npc-{ch['index']:03d}-{slugify(first)}"
        cjk = ch["index"] % 15 == 7
        docs, item_docs, checks = [], [], []
        chron_no = 0
        for vol_no, kind in enumerate(ch["kinds"], start=1):
            if kind == "chronicle":
                chron_no += 1
            target = next(targets) if kind in ("single", "chronicle") else 0
            if kind == "single":
                fname, dname = f"{ch['index']:03d}-{slug}.pdf", f"{ch['name']} dossier"
            elif kind == "chronicle":
                fname, dname = f"{ch['index']:03d}-{slug}-v{vol_no}-chronicle-{chron_no}.pdf", f"{ch['name']}: Chronicle {chron_no}"
            else:
                fname, dname = f"{ch['index']:03d}-{slug}-v{vol_no}-{kind}.pdf", f"{ch['name']}: {VOLUME_TITLES[kind]}"
            path = os.path.join(pdf_dir, fname)
            build_doc(path, ch, kind, vol_no, chron_no, target, cjk and vol_no == 1, rng, styles)
            url = f"{base_url}/{fname}"
            check = verify(path, ch, kind, chron_no) or {}
            entry = {
                "character_index": ch["index"], "customId": custom_id, "volume": vol_no, "of": ch["doc_count"], "kind": kind,
                "file": f"pdfs/{fname}", "url": url, "size_bytes": os.path.getsize(path),
                "pages": check.get("pages"), "facts_extractable": check.get("facts_extractable"),
                "has_cjk_section": cjk and vol_no == 1,
            }
            docs.append(entry)
            documents_out.append(entry)
            item_docs.append({"url": url, "name": dname, "type": "pdf"})
            # retrieval checks, each tagged with the one file that holds the answer
            if kind in ("single", "dossier"):
                checks += [
                    {"question": f"What is {first}'s favourite dish?", "expect": ch["favorite_dish"], "source_file": entry["file"]},
                    {"question": f"What is {first}'s lucky number?", "expect": str(ch["lucky_number"]), "source_file": entry["file"]},
                    {"question": f"What is the name of {first}'s pet?", "expect": ch["pet_name"], "source_file": entry["file"]},
                ]
            if kind in ("single", "relationships"):
                checks += [
                    {"question": f"What is the password to {first}'s workshop?", "expect": ch["password"], "source_file": entry["file"]},
                    {"question": f"Who is {first}'s rival?", "expect": ch["rival"], "source_file": entry["file"]},
                    {"question": f"Who taught {first} the trade?", "expect": ch["mentor"], "source_file": entry["file"]},
                ]
            if kind == "chronicle":
                thing, pname = ch["possessions"][chron_no - 1]
                checks.append({"question": f"What does {first} call the {thing}?", "expect": pname, "source_file": entry["file"]})
            print(f"{fname:56s} {kind:13s} pages={check.get('pages'):>3} ok={check.get('facts_extractable')} {entry['size_bytes']:>7d}B")
        characters_out.append({
            "index": ch["index"], "customId": custom_id, "name": ch["name"], "document_count": ch["doc_count"],
            "documents": docs,
            "facts": {k: ch[k] for k in ("role", "setting", "tagline", "traits", "speech", "age", "hometown", "favorite_dish",
                                         "pet_name", "pet_species", "lucky_number", "password", "mentor", "rival", "friend",
                                         "goal", "fear", "secret")},
            "possessions": [{"thing": t, "called": p} for t, p in ch["possessions"]],
            "retrieval_checks": checks,
        })
        items.append({
            "customId": custom_id,
            "persona": {
                "name": ch["name"],
                "tagline": ch["tagline"],
                "personality": f"{cap(ch['traits'])}. {first} {ch['speech']}.",
                "background": f"{cap(ch['role'])} of {ch['setting']}, originally from {ch['hometown']}. "
                              f"Detailed lore, including verified facts, is in the attached "
                              f"{'dossier' if ch['doc_count'] == 1 else f'{ch['doc_count']}-volume collection'}.",
            },
            "documents": item_docs,
        })

    dist = {}
    for ch in chars:
        dist[ch["doc_count"]] = dist.get(ch["doc_count"], 0) + 1
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": SEED, "base_url": base_url, "pdf_count": len(documents_out), "character_count": len(chars),
                   "characters_by_document_count": {str(k): v for k, v in sorted(dist.items())},
                   "characters": characters_out, "documents": documents_out}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "urls.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(e["url"] for e in documents_out) + "\n")
    with open(os.path.join(out_dir, "batch_request.json"), "w", encoding="utf-8") as f:
        json.dump({"requests": items}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "batch_request_10.json"), "w", encoding="utf-8") as f:
        json.dump({"requests": items[:10]}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "batch_request_multi.json"), "w", encoding="utf-8") as f:
        json.dump({"requests": [it for it in items if len(it["documents"]) > 1]}, f, indent=2, ensure_ascii=False)
    total = sum(e["size_bytes"] for e in documents_out)
    pages = sum(e["pages"] or 0 for e in documents_out)
    bad = [e["file"] for e in documents_out if e["facts_extractable"] is False]
    print(f"\n{len(documents_out)} PDFs for {len(chars)} characters {dist}, {total / 1e6:.1f} MB, {pages} pages total; "
          f"verification failures: {bad or 'none'}")
    print(f"batch_request.json: {len(items)} items, {sum(len(i['documents']) for i in items)} documents; "
          f"first 10 items have document counts {[len(i['documents']) for i in items[:10]]}")


if __name__ == "__main__":
    main()
