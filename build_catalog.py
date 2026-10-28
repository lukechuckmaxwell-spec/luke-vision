#!/usr/bin/env python3
"""Build catalog.json for Luke Vision from the Internet Archive.

Standard library only.  Run:  python3 build_catalog.py
Rebuild only some channels:   python3 build_catalog.py "Old TV" "MonsterVision"
"""

import html
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# The classic, mostly public-domain collections the holiday channels draw from.
# Searching all of archive.org for "halloween" or "christmas" mostly finds
# uploads of modern studio films. Holiday queries match on title only, because
# subject tags pull in loosely related items (e.g. Prelinger home movies).
CLASSIC_POOL = ("collection:(feature_films OR classic_cartoons OR classic_tv OR television"
                " OR classic_tv_commercials OR SciFi_Horror OR Comedy_Films)")
# Anything animated: the classic cartoons collection plus items tagged as cartoons.
CARTOONS = ("((collection:classic_cartoons OR subject:cartoon OR subject:cartoons"
            " OR subject:animation OR subject:animated)"
            " AND NOT title:(opening OR commercial OR commercials OR intro OR trailer"
            " OR bumper OR bumpers OR promo OR promos OR speedpaint OR yaoi OR review"
            " OR reaction OR explained OR outtakes OR \"behind the scenes\" OR r18 OR \"r-18\" OR mmd OR nollywood OR nigerian)"
            " AND NOT subject:(mmd OR hentai OR nsfw OR adult OR erotic OR nollywood))")

# Superhero channels: cartoon, TV and serial collections only. Searching everywhere finds
# rips of recent studio films, CapCut templates, music videos and worse.
HERO_COLLECTIONS = ("collection:(classic_cartoons OR more_animation OR animation_unsorted"
                    " OR saturdaymorningcartoons OR childrenstelevision OR television_inbox OR vhstvshows"
                    " OR vhskids OR classic_tv OR classic_tv_1940s OR classic_tv_1950s OR classic_tv_1960s"
                    " OR classic_tv_1970s OR feature_films OR feature_films_unsorted OR short_films"
                    " OR film_serials)")
HERO_NOT = ('NOT title:("robin hood" OR capcut OR template OR "music video" OR porn OR crank'
            " OR tetsuo OR amazons OR trailer OR commercial OR commercials OR review OR reaction"
            " OR speedpaint OR mmd OR r18 OR pranks OR elsa OR frozen OR \"love drug\" OR hogan*"
            " OR blooper OR bloopers OR komment OR oprah OR \"behind the scenes\""
            ' OR "return of superman" OR "returnof superman" OR texture OR tutorial OR "team toon")'
            # Foreign-language dubs.
            ' AND NOT title:(dub OR dubbed OR dublado OR dansk OR "pt-pt" OR capitulo OR german'
            " OR spanish OR latino OR castellano OR turkish OR präsentiert OR svenska OR svensk"
            ' OR mascara OR "la série" OR "la serie" OR reklam)'
            " AND NOT subject:(hentai OR nsfw OR adult OR porn OR erotic OR mmd)"
            # A second upload of the 1944 Captain America serial (captain_america_epN is kept).
            " AND NOT identifier:CaptainAmerica1944Chapter*")
HERO_POOL = f"{HERO_COLLECTIONS} AND {HERO_NOT}"

# Batman is also well stocked in general collections that are otherwise mostly film rips,
# so Batman titles get searched there too, minus the live-action studio films, game
# footage and other strays found in those collections.
BATMAN_TITLES = ('(title:batman OR title:catwoman OR title:"harley quinn" OR title:riddler'
                 ' OR title:"two-face" OR title:"mr. freeze" OR title:"gotham girls"'
                 ' OR title:"mask of the phantasm" OR title:"brave and the bold")')
BATMAN_EXTRA = (f"{BATMAN_TITLES} AND collection:(opensource_movies OR vhsmovies OR comics_inbox"
                ' OR dvdtray OR dvdtray_inbox OR "video-home-system" OR "colorized-movies")'
                ' AND NOT title:(returns OR forever OR "dawn of justice" OR "dark knight" OR begins'
                ' OR lego OR "5 seconds" OR yts OR yify OR webrip OR "v superman" OR "vs superman"'
                ' OR "star trek" OR truth OR "right wing" OR koi OR nes OR speedrun OR "silent motion")')

# Retro anime: named classic shows only, never tags. Searching by tag turns up adult
# OVAs, so every anime query also carries strict adult, modern-remake and dub filters.
ANIME_COLLECTIONS = ('collection:(anime_miscellaneous OR animepacks OR saturdaymorningcartoons'
                     ' OR television_inbox OR vhstvshows OR vhskids OR animation_unsorted OR more_animation'
                     ' OR childrenstelevision OR "miscellaneous-japanese-tv")')
ANIME_NOT = ('NOT collection:(adultvhs OR hentaiarchive)'
             ' AND NOT subject:(hentai OR nsfw OR adult OR porn OR erotic OR ecchi OR yuri OR yaoi OR lemon OR "18+")'
             ' AND NOT title:(hentai OR porn OR r18 OR "r-18" OR ecchi OR uncensored OR lemon OR lolita OR yuri'
             ' OR yaoi OR lesbian OR kissing OR maid OR mmd OR amv OR abridged OR capcut OR template OR trailer'
             ' OR review OR reaction OR "music video" OR "music library" OR absalon OR parody'
             ' OR "field trip" OR subtitulado)'
             # Modern remakes and sequels.
             ' AND NOT title:(legendary OR "dragon ball super" OR "dragon ball heroes" OR kai OR seed'
             ' OR infinity OR crystal OR live OR "speed racer x" OR "shin mazinger" OR "cyborg soldier"'
             ' OR crowds OR "next generation" OR saintia OR delta OR kakarot'
             ' OR "pretty guardian" OR raretoku'   # 2003 live-action Sailor Moon
             ' OR 2001 OR 2002 OR 2003 OR 2004 OR 2005 OR 2006 OR 2007 OR 2008 OR 2009 OR 2010 OR 2011'
             ' OR 2012 OR 2013 OR 2014 OR 2015 OR 2016 OR 2017 OR 2018 OR 2019 OR 2020 OR 2021 OR 2022'
             ' OR 2023 OR 2024 OR 2025 OR 2026)'
             # English dubs and Japanese originals only, going by the item's language field.
             # (Blocking dub words in titles never caught them all: there are too many languages.)
             " AND language:(eng OR english OR jpn OR japanese)")

# Classic-era (2001-2007) Adult Swim. Filters skip porn but not the word "adult", which
# would remove everything titled "adult swim"; years after 2007 are left out.
AS_LATER = " OR ".join(str(y) for y in range(2008, 2027))
AS_NOT = ("NOT collection:(adultvhs OR hentaiarchive OR prelinger OR prelingerhomemovies OR home_movies"
          " OR short_films OR ourmedia OR xfrcollective OR computerchronicles)"
          " AND NOT subject:(hentai OR porn OR nsfw OR xxx)"
          ' AND NOT title:(porn OR hentai OR fanmade OR "fan made" OR reaction OR review OR "toy story"'
          f" OR {AS_LATER})"
          # Later shows and fan-made bumps whose titles carry no year.
          ' AND NOT title:("user made" OR "fan bump" OR custom OR 2010s OR "children\'s hospital"'
          ' OR "childrens hospital" OR frankenhole OR poker OR festival OR "million dollar extreme"'
          ' OR "problem solverz" OR "citizen siege" OR trailer OR location OR "rick and morty"'
          ' OR "anime cast" OR gta OR goanimate OR vaccines OR "disney princess" OR interview'
          ' OR podcast OR stream OR livestream OR "gypsy crusader" OR "if the")'
          # Foreign feeds and dubs.
          " AND NOT title:(dublado OR mexico OR méxico OR grabaciones OR latino OR español"
          ' OR espanol OR latinoamérica OR "pt-br" OR brasil OR doblaje)')

# Classic sports: full games from before 2008. The title must carry a year from 1920 to 2007
# (and none later), which also keeps out the many recent full-game uploads.
SPORTS_OLD = ("title:(192? OR 193? OR 194? OR 195? OR 196? OR 197? OR 198? OR 199? OR 200?)"
              f" AND NOT title:({AS_LATER})")
# Short clips (ads, intros, interviews) are dropped by length, so this only names long things
# that aren't games: video games, studio shows, fan footage and mixed TV recordings.
SPORTS_NOT = ('NOT title:(highlights OR highlight OR halftime OR "half time" OR pregame OR "pre game"'
              ' OR postgame OR "post game" OR gameplay OR longplay OR playthrough OR "lets play"'
              ' OR "season mode" OR nintendo OR sega OR genesis OR snes OR playstation OR ps2 OR "ps 2"'
              " OR ps3 OR xbox OR gamecube OR vgc OR madden OR tecmo OR 2k OR blitz OR hitz OR jam"
              ' OR slugfest OR "high heat" OR shootout OR courtside OR "quarterback club" OR "face off"'
              " OR primetime OR today OR awards OR parade OR champions OR greatest OR history OR follies"
              " OR cheerleaders OR biography OR news OR newscast OR nightline OR trek OR \"cartoon network\""
              " OR oprah OR radio OR watched OR poker OR golf OR \"little league\" OR ripken OR youth"
              ' OR "high school" OR college OR ncaa OR softball OR wrestling OR "world series of"'
              ' OR "around the world" OR "enchanted world" OR podcast OR reaction OR preview OR practice'
              " OR training OR clips OR seasons OR movie OR film OR films OR animatrix OR footage"
              " OR interviews OR celebration)"
              # Season film collections and video-game footage with plain titles.
              " AND NOT identifier:(afpp-* OR nhl-2001-*)")
# Games run 2-4 hours, so 48 hours of them to get a couple of dozen per channel.
SPORTS_OPTS = {"whole": True, "min_dur": 40 * 60, "max_dur": 5 * 60 * 60, "target_dur": 48 * 60 * 60}

# Identifiers that slipped past the queries but don't belong. Add your own here;
# find an item's identifier in catalog.json or in its archive.org/details/<id> URL.
EXCLUDE_IDS = {
    "youtube-Jutv8LijAWg",                          # adult fan art
    "which-disney-halloween-tv-special-is-which",   # explainer video, not a cartoon
    "dukes-xmas",                                   # live action
    "the-sons-of-mistletoe-2001-christmas-family",  # live action
    "youtube-YMt8ls2AfMU",                          # slasher behind-the-scenes reel
    "roosterteeth-49650",                           # Jason vs. Michael Myers fight
    "x-men-nightofthesentinels-halloween92cut-2025",  # not Halloween-themed
    "vintage-tv-holiday-specials-halloween-christmas-1996-whbf-wqad",  # promo reel
    "merriemelodiesdisneycartoons1929-1",           # third copy of The Skeleton Dance
    "the-skeleton-dance_1929",                      # second copy of The Skeleton Dance
    "spider-man-marathon-gi-joe-g-gundam-batman-cartoon-network-abc-family-broadcast-2003-woc",  # mostly not DC
    "alyasbatmanenrobin",                           # Tagalog-language parody
    "batman-mustan-kostajan-paluu",                 # Finnish dub
    "batman.-1943.",                                # second copy of the 1943 Batman serial
    "batmanbeyond-rebirth-restored",                # second copy of Batman Beyond: The Movie
    "40sSupermanCartoonCopiedInskyCaptainAndTheWorldOfTomorrow",  # comparison clip
    "CaptainAmericaSerialCh13-15",                  # another copy of the Captain America serial
    "spiderman-2-komment-2009-bol-2.resz-18",       # 18+ video-game commentary
    "the-phantom-planet-full-movie-public-domain-1",  # sci-fi film with a Superman short attached
    "iron-man-1951_202309",                         # 1951 boxing drama, not Marvel
    "dragon-ball-z-gohan-y-trunks-un-futuro-diferente",  # Spanish dub
    "dragon-ball-gt-vhs-pt",                        # Portuguese dub
    "frankenhole-halloween-2011-4",                 # mostly 2010-11 shows (Children's Hospital)
    "super-bowl-xxxi-commercials-kasa-01-26-1997",  # the ads, not the game
    "coatx-Eddie_Robinson_-_Oldest_living_New_York_Yankee_and_the_1948_World_Series",  # interview
    "toronto-blue-jays-1992-world-series",          # season highlight video
}
# Checked against every upload title and every episode title taken from an upload.
EXCLUDE_TITLE_WORDS = (
    "aoi kaze no hope",         # music video with no telltale word in the title
    "s05e00 boston",            # extra copies of the unaired Aqua Teen episode "Boston"
    " interview",               # interviews and podcasts tucked into series uploads
    "podcast",
)

# Channel name -> (Internet Archive search query or a list of them (an entry may be
#                  (query, max results) to cap one search), one-line channel description,
#                  optional overrides: {"min_dur": seconds, "target_dur": seconds,
#                  "max_eps": episodes to take from an upload holding a whole series,
#                  "include": {identifier: videos to take or None} always added,
#                  whatever the search finds, "max_dur": seconds, "bumps": a search for
#                  short bumpers to play between shows}, "whole": True to play every video
#                  of an upload in order, for games split into parts; then min_dur and
#                  max_dur apply to the whole game).
# NOTE: verify that each collection exists (and holds video) before relying on it
# by opening https://archive.org/details/<collection> in a browser. Collections
# get renamed or merged; a missing one just produces an empty channel.
CHANNELS = {
    "Saturday Cartoons": (
        "collection:classic_cartoons",
        "Golden-age animation: Betty Boop, Popeye, Superman and friends, all morning long.",
    ),
    "Ephemeral Films": (
        "collection:prelinger",
        "Educational, industrial and advertising films from the Prelinger Archives.",
    ),
    "Commercial Break": (
        "collection:classic_tv_commercials",
        "Nothing but vintage ads, jingles and station breaks.",
    ),
    "Creature Feature": (
        "collection:SciFi_Horror",
        "B-movie monsters, mad scientists and flying saucers from the drive-in era.",
    ),
    "MonsterVision": (
        '(title:monstervision OR title:"monster vision")',
        "Reruns of TNT's late-night horror show, hosted by Joe Bob Briggs.",
    ),
    "Old TV": (
        "collection:classic_tv",
        "Sitcoms, westerns and detective shows from the early days of broadcast TV.",
    ),
    "Halloween Haunts": (
        '(title:halloween OR title:"trick or treat" OR title:pumpkin OR title:haunted'
        ' OR title:spooks OR title:"sleepy hollow" OR title:"headless horseman")'
        f" AND {CLASSIC_POOL}",
        "Spooky specials, Halloween episodes and trick-or-treat cartoons.",
    ),
    "Christmas Classics": (
        "(title:christmas OR title:xmas OR title:santa OR title:scrooge OR title:noel"
        f' OR title:reindeer) AND NOT title:"santa fe" AND {CLASSIC_POOL}',
        "Christmas Carols, holiday cartoons and Christmas episodes of classic TV.",
    ),
    "Halloween Toons": (
        '(title:halloween OR title:"trick or treat" OR title:pumpkin OR title:haunted'
        ' OR title:spooks OR title:spooky OR title:"skeleton dance" OR title:casper'
        ' OR title:"friendly ghost" OR title:"lonesome ghosts" OR title:"sleepy hollow"'
        f' OR title:"headless horseman") AND {CARTOONS}',
        "Nonstop Halloween cartoons: Casper, Betty Boop, skeleton dances and Great Pumpkins.",
        {"min_dur": 180},
    ),
    "Christmas Toons": (
        "(title:christmas OR title:xmas OR title:santa OR title:scrooge OR title:reindeer"
        ' OR title:snowman OR title:frosty OR title:rudolph OR title:"night before")'
        f' AND NOT title:"santa fe" AND {CARTOONS}',
        "Round-the-clock Christmas cartoons, from Rudolph and Frosty to Mickey's Christmas Carol.",
        {"min_dur": 180},
    ),
    "DC Heroes": (
        # Two searches, merged: as one query this is too long, and archive.org then
        # silently returns nothing.
        [
            "(title:superman OR title:\"wonder woman\" OR title:aquaman"
            ' OR title:"justice league" OR title:"green lantern" OR title:shazam OR title:"super friends"'
            ' OR title:superfriends OR title:"teen titans" OR title:supergirl OR title:batgirl'
            f" OR {BATMAN_TITLES}) AND {HERO_COLLECTIONS} AND {HERO_NOT}",
            f"({BATMAN_EXTRA}) AND {HERO_NOT}",
        ],
        "Superman, Batman and his rogues gallery, from 1940s serials to Saturday-morning cartoons.",
        # 24 hours and up to 6 episodes per complete-series upload, so Batman has room.
        {"min_dur": 180, "max_eps": 6, "target_dur": 24 * 60 * 60,
         "include": {   # identifier -> videos to take (None = the channel's max_eps)
             "the-batman-superman-movie": 1,            # The Batman Superman Movie (1997)
             "batman-1966_202112": 1,                   # Batman (1966): Movie
             "the-new-batman-adventures-episode-23-beware-the-creeper": None,  # Batman The Animated Series
             "Batman_The_Animated_Series_1992-1995": None,  # Batman: The Animated Series (1992-1995)
             # Another TAS DVD upload titled "Batman the animated series" (odd identifier).
             "dragon-ball-z-1989-2018-the-complete-uncut-series-16-dbz-movies-4-ovas-8-tv-spec": None,
         }},
    ),
    "Marvel Heroes": (
        '(title:"spider-man" OR title:spiderman OR title:"x-men" OR title:hulk OR title:"iron man"'
        ' OR title:"captain america" OR title:"fantastic four" OR title:"mighty thor"'
        # "daredevil" and "spider-woman" are left out: they mostly match unrelated old films.
        ' OR title:"marvel super heroes" OR title:"silver surfer" OR title:wolverine)'
        f" AND {HERO_POOL}",
        "Spider-Man, the X-Men, the Hulk and Captain America, from 1940s serials to 90s cartoons.",
        {"min_dur": 180},
    ),
    "Retro Anime": (
        # Several searches (archive.org returns nothing for one that's too long). Dragon Ball
        # gets its own; mixed in, its many uploads crowd out everything else.
        [
            '(title:"astro boy" OR title:astroboy OR title:"tetsuwan atom" OR title:"speed racer"'
            ' OR title:gigantor OR title:kimba OR title:"star blazers" OR title:"space battleship yamato"'
            ' OR title:robotech OR title:voltron OR title:"battle of the planets" OR title:"g-force"'
            ' OR title:gatchaman OR title:"captain harlock" OR title:macross OR title:mazinger'
            ' OR title:"galaxy express" OR title:"marine boy" OR title:"prince planet")'
            f" AND {ANIME_COLLECTIONS} AND {ANIME_NOT}",
            '(title:"lupin iii" OR title:"urusei yatsura" OR title:"city hunter" OR title:ranma'
            ' OR title:"sailor moon" OR title:"mobile suit gundam" OR title:"saint seiya"'
            ' OR title:"dirty pair" OR title:"getter robo" OR title:"cyborg 009" OR title:"candy candy"'
            ' OR title:starzinger OR title:"cowboy bebop" OR title:"captain tsubasa" OR title:"tranzor z")'
            f" AND {ANIME_COLLECTIONS} AND {ANIME_NOT}",
            # Whole-series and movie uploads only (one uploader posted every DBZ episode
            # separately), and just the 20 most popular, so Dragon Ball doesn't take over.
            (f'title:"dragon ball" AND {ANIME_COLLECTIONS} AND {ANIME_NOT}'
             ' AND NOT identifier:videoplaytv* AND NOT title:episode', 20),
        ],
        "Saturday-morning and late-night anime from the 60s to the 90s: Astro Boy, Speed Racer,"
        " Robotech, Sailor Moon, Dragon Ball and more.",
        {"min_dur": 180, "max_eps": 3, "target_dur": 24 * 60 * 60},
    ),
    "Adult Swim Classic": (
        [
            # Off-air recordings of whole nights and blocks, with the original bumps and ads.
            '(title:"adult swim" OR title:"[adult swim]")'
            " AND NOT title:(bump OR bumps OR bumper OR bumpers OR promo OR promos)"
            f" AND {AS_NOT}",
            # Episodes of the classic-era originals. ("Home Movies" alone matches real home movies.)
            '(title:"space ghost coast to coast" OR title:"aqua teen hunger force" OR title:"sealab 2021"'
            ' OR title:"harvey birdman" OR title:"brak show" OR title:squidbillies OR title:"venture bros"'
            ' OR title:"tom goes to the mayor" OR title:"perfect hair forever" OR title:"12 oz mouse"'
            ' OR title:"moral orel" OR title:"frisky dingo" OR title:minoriteam OR title:metalocalypse'
            ' OR title:"stroker and hoop" OR title:"saul of the mole men" OR title:"lucy, the daughter"'
            ' OR (title:"home movies" AND title:(season OR complete OR cartoon OR episode OR s01)))'
            f" AND {AS_NOT}",
        ],
        "The classic [adult swim] of 2001 to 2007: Space Ghost, Aqua Teen, Sealab, Harvey Birdman,"
        " late-night anime and the bumps in between.",
        {"min_dur": 180, "max_dur": 4 * 60 * 60, "max_eps": 3, "target_dur": 24 * 60 * 60,
         # A bump between every show, like the real thing.
         "bumps": '(title:"adult swim" OR title:"[adult swim]") AND title:(bump OR bumps OR bumper'
                  f' OR bumpers) AND {AS_NOT}'},
    ),
    "NFL Classics": (
        '(title:nfl OR title:"super bowl" OR title:"monday night football" OR title:"afl championship"'
        f' OR title:"afc championship" OR title:"nfc championship") AND {SPORTS_OLD} AND {SPORTS_NOT}',
        "Old NFL broadcasts: Super Bowls, Monday Night Football and playoff games from the 50s to the 2000s.",
        SPORTS_OPTS,
    ),
    "NBA Classics": (
        f'(title:nba OR title:"nba finals") AND {SPORTS_OLD} AND {SPORTS_NOT}',
        "Vintage NBA Finals, playoff battles and All-Star Games: Magic, Bird, Jordan and more.",
        SPORTS_OPTS,
    ),
    "NHL Classics": (
        '(title:nhl OR title:"stanley cup" OR title:"hockey night in canada")'
        f" AND {SPORTS_OLD} AND {SPORTS_NOT}",
        "Old-time hockey: Stanley Cup Finals, playoff games and Hockey Night in Canada.",
        SPORTS_OPTS,
    ),
    "MLB Classics": (
        '(title:mlb OR title:"world series" OR title:"major league baseball" OR title:alcs'
        f" OR title:nlcs) AND {SPORTS_OLD} AND {SPORTS_NOT}",
        "World Series, playoff and All-Star Games from baseball's past, ballpark organ not included.",
        SPORTS_OPTS,
    ),
}

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{id}"
DOWNLOAD_URL = "https://archive.org/download/{id}/{name}"
THUMB_URL = "https://archive.org/services/img/{id}"   # the item's cover image

ROWS = 150
SEED = 1977                   # fixed seed -> reproducible lineup
MIN_DUR = 30                  # seconds
MAX_DUR = 2 * 60 * 60
TARGET_DUR = 12 * 60 * 60     # stop filling a channel at ~12 hours
DESC_MAX = 280                # characters of description kept for the guide
DELAY = 0.3                   # politeness pause between requests
TIMEOUT = 30
USER_AGENT = "LukeVision/1.0 (self-hosted catalog builder; python-urllib)"
OUT_PATH = Path(__file__).resolve().parent / "catalog.json"


def get_json(url, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def search(query, rows=ROWS):
    params = {
        "q": f"({query}) AND mediatype:movies",
        "fl[]": "identifier",
        "sort[]": "downloads desc",
        "rows": rows,
        "page": 1,
        "output": "json",
    }
    docs = get_json(SEARCH_URL, params).get("response", {}).get("docs", [])
    return [d["identifier"] for d in docs if d.get("identifier")]


def parse_length(value):
    """Seconds from '123.45', 'mm:ss' or 'hh:mm:ss'; None if unusable."""
    if value is None:
        return None
    try:
        parts = [float(p) for p in str(value).strip().split(":")]
    except ValueError:
        return None
    if not 1 <= len(parts) <= 3:
        return None
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds if seconds > 0 else None


def pick_file(files, min_dur=0, max_dur=float("inf")):
    """Best .mp4 with a usable length: derivatives first, then H.264 (plays in every
    browser), then the longest (the feature, not its trailer or a disc menu)."""
    best, best_key = None, None
    for f in files:
        name = f.get("name", "")
        if not name.lower().endswith(".mp4"):
            continue
        dur = parse_length(f.get("length"))
        if dur is None or not min_dur <= dur <= max_dur:
            continue
        key = (f.get("source") == "derivative", "h.264" in str(f.get("format", "")).lower(), dur)
        if best_key is None or key > best_key:
            best, best_key = (name, dur), key
    return best


def pick_files(files, limit=1, min_dur=0, max_dur=float("inf")):
    """Up to `limit` distinct videos from one item, spread evenly across it (by file name),
    for uploads that hold a whole series. Each video's best copy is picked as in pick_file.
    Videos outside [min_dur, max_dur] (disc menus, whole-disc rips) are dropped first."""
    if limit <= 1:
        best = pick_file(files, min_dur, max_dur)
        return [best] if best else []
    videos = best_copies(files, min_dur, max_dur)
    if len(videos) > limit:
        videos = [videos[round(i * (len(videos) - 1) / (limit - 1))] for i in range(limit)]
    return videos


PIECE_MIN = 4 * 60   # seconds; shorter files in a whole-game upload are clips, not parts
GAME_PART_MAX = 100 * 60   # an upload's videos all shorter than this are parts of one game


def pick_whole(files, min_dur=0, max_dur=float("inf")):
    """Every video of an upload in file-name order ("pt. 1" ... "pt. 9", or a set of games),
    until the next one would pass max_dur in total; nothing if the total is under min_dur."""
    picked, total = [], 0.0
    for name, dur in best_copies(files, PIECE_MIN, max_dur):
        if picked and total + dur > max_dur:
            break
        picked.append((name, dur))
        total += dur
    return picked if total >= min_dur else []


def best_copies(files, min_dur, max_dur):
    """(name, dur) of each distinct video in [min_dur, max_dur], in natural file-name order."""
    copies = {}   # "show s01e01" -> (name, dur, key); x.mp4, x.ia.mp4, x_512kb.mp4 are one video
    for f in files:
        name = f.get("name", "")
        if not name.lower().endswith(".mp4"):
            continue
        dur = parse_length(f.get("length"))
        if dur is None or not min_dur <= dur <= max_dur:
            continue
        key = (f.get("source") == "derivative", "h.264" in str(f.get("format", "")).lower())
        video = re.sub(r"(_512kb|\.ia)?\.mp4$", "", name, flags=re.I).lower()
        if video not in copies or key > copies[video][2]:
            copies[video] = (name, dur, key)
    # Natural order, so "pt. 10" comes after "pt. 9".
    natural = lambda c: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", c[0].lower())]
    return [(name, dur) for name, dur, _ in sorted(copies.values(), key=natural)]


RELEASE_JUNK = r"[._ ([-](?:2160p|1080p|720p|480p|blu-?ray|web-?dl|webrip|dvdrip|x26[45]|hevc|h\.?26[45])\b"


def episode_title(show, filename):
    """'Batman.The.Animated.Series.S01E02.On.Leather.Wings.1080p.BluRay.x264.mp4'
    -> 'Batman The Animated Series S01E02 On Leather Wings'."""
    stem = re.sub(r"(_512kb|\.ia)?\.mp4$", "", filename.rsplit("/", 1)[-1], flags=re.I)
    stem = re.split(RELEASE_JUNK, stem, maxsplit=1, flags=re.I)[0]
    stem = re.sub(r"[._\s]+", " ", stem)
    stem = re.sub(r"\s*[(\[][^)\]]*$", "", stem).strip(" -")   # unclosed "(1993 ..." left by the cut
    if not stem:
        return show
    show_word = (title_key(show).split() or [""])[0]
    return stem if show_word and show_word in stem.lower() else f"{show} – {stem}"


def first(value):
    """Metadata fields are sometimes lists; take the first entry."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def clean_description(value):
    """Plain-text, length-limited description; archive.org descriptions are often HTML."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    text = re.sub(r"<br\s*/?>|</p>", " ", str(value or ""), flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > DESC_MAX:
        text = text[:DESC_MAX].rsplit(" ", 1)[0].rstrip(",;:.-") + "…"
    return text


JUNK_WORDS = {"the", "a", "hd", "sd", "upgrade", "widescreen", "video", "quality",
              "remastered", "restored", "full", "movie", "film", "dvd", "rip", "brrip",
              "bd", "1080p", "720p", "480p", "x264", "h264", "mp4"}


def title_key(title):
    """Rough identity of a title, so re-uploads of the same film count as one."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in JUNK_WORDS and not re.fullmatch(r"(19|20)\d\d|\d{1,2}", w))


def fmt(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def is_duplicate(key, seen):
    """Same title, one title inside the other ("[VHS] Dr. Seuss: How the Grinch Stole
    Christmas!, narrated by..." vs "How the Grinch Stole Christmas"), or the same first
    six words ("Casper Comes to Clown (UK VHS)" vs "Casper Comes to Clown (VHSrip)")."""
    head = key.split()[:6]
    for k in seen:
        if k == key:
            return True
        short, long_ = sorted((k, key), key=len)
        if len(short) >= 20 and short in long_:
            return True
        if len(head) == 6 and k.split()[:6] == head:
            return True
    return False


GAME_JUNK = {"vhs", "broadcast", "complete", "original", "nfl", "nba", "nhl", "mlb", "vs", "at",
              "versus", "with", "commercials", "commericals", "woc", "tape", "recording"}
PART_RE = re.compile(r"[\s(\[-]*\b(?:pt|part)\.?\s*(\d+)(?:\s*(?:/|of)\s*\d+)?[)\]]?", re.I)


def game_key(title):
    """Like title_key, but keeps years, dates and game numbers: they tell games apart."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in JUNK_WORDS and w not in GAME_JUNK)


def split_part(title):
    """'Redskins vs. Seahawks, 1992 (pt. 2)' -> ('Redskins vs. Seahawks, 1992', 2); else part 0."""
    m = PART_RE.search(title)
    return (PART_RE.sub("", title, count=1).strip(" -"), int(m.group(1))) if m else (title, 0)


def is_duplicate_game(key, seen):
    """Same game, or one title inside the other. No first-words rule: "1991 NBA Finals
    Bulls vs Lakers Game 1" and "... Game 2" share them."""
    for k in seen:
        short, long_ = sorted((k, key), key=len)
        if k == key or (len(short) >= 20 and short in long_):
            return True
    return False


BUMP_MIN, BUMP_MAX = 5, 5 * 60   # seconds; a bump compilation longer than this is skipped


def fetch_bumps(query, count, rng):
    """Up to `count` short bumpers (a few per upload) to slot between shows."""
    try:
        ids = [i for i in search(query) if i not in EXCLUDE_IDS]
    except Exception as exc:
        print(f"  ! bump search failed: {exc}")
        return []
    time.sleep(DELAY)
    rng.shuffle(ids)
    bumps = []
    for ident in ids:
        if len(bumps) >= count:
            break
        try:
            meta = get_json(METADATA_URL.format(id=urllib.parse.quote(ident)))
            for filename, dur in pick_files(meta.get("files") or [], 3, BUMP_MIN, BUMP_MAX):
                bumps.append({
                    "id": ident,
                    "title": "Bump: " + str(first((meta.get("metadata") or {}).get("title")) or ident),
                    "dur": round(dur, 2),
                    "url": DOWNLOAD_URL.format(id=ident, name=urllib.parse.quote(filename)),
                    "desc": "",
                    "thumb": THUMB_URL.format(id=urllib.parse.quote(ident)),
                })
        except Exception as exc:
            print(f"  ! bump {ident}: {exc}")
        finally:
            time.sleep(DELAY)
    print(f"  {len(bumps)} bumps")
    return bumps[:count]


def build_channel(name, query, min_dur=MIN_DUR, target_dur=TARGET_DUR, max_eps=1, include=None,
                  max_dur=MAX_DUR, bumps=None, whole=False):
    include = include or {}
    queries = [q if isinstance(q, tuple) else (q, ROWS)
               for q in (query if isinstance(query, list) else [query])]
    print(f"\n== {name}  [{' | '.join(q for q, _ in queries)}]")
    ids = []
    for q, rows in queries:
        try:
            ids += [i for i in search(q, rows) if i not in ids]
        except Exception as exc:
            print(f"  ! search failed: {exc}")
            return []
        time.sleep(DELAY)
    print(f"  {len(ids)} search results")
    if not ids:
        print("  ! nothing found - does this collection exist?")

    rng = random.Random(f"{SEED}:{name}")
    ids = [i for i in ids if i not in EXCLUDE_IDS and i not in include]
    rng.shuffle(ids)
    ids = list(include) + ids   # must-haves first, so the time limit can't crowd them out

    items, total, seen = [], 0.0, set()
    game_of = {}   # whole mode: identifier -> (game, part number), to keep a game's parts together
    for n, ident in enumerate(ids, 1):
        if total >= target_dur:
            break
        tag = f"  [{n}/{len(ids)}]"
        try:
            meta = get_json(METADATA_URL.format(id=urllib.parse.quote(ident)))
            files = meta.get("files") or []
            picked = (pick_whole(files, min_dur, max_dur) if whole
                      else pick_files(files, include.get(ident) or max_eps, min_dur, max_dur))
            if not picked:
                print(f"{tag} skip {ident}: no .mp4 with a usable length")
                continue
            info = meta.get("metadata") or {}
            title = str(first(info.get("title")) or ident).strip() or ident
            if any(w in title.lower() for w in EXCLUDE_TITLE_WORDS):
                print(f"{tag} skip {ident}: excluded title")
                continue
            desc = clean_description(info.get("description"))
            series = len(picked) > 1
            if whole:
                # One game per upload (or the first few of a set of games), checked once.
                game, part = split_part(title)
                key = game_key(game) + (f" part {part}" if part else "")
                if key and is_duplicate_game(key, seen):
                    print(f"{tag} skip {ident}: duplicate of '{title[:50]}'")
                    continue
                seen.add(key)
                game_of[ident] = (game_key(game), part)
                # Pieces all shorter than a game are parts of one; otherwise they're games.
                in_parts = all(dur < GAME_PART_MAX for _, dur in picked)
            for n_piece, (filename, dur) in enumerate(picked, 1):
                if total >= target_dur:
                    break
                if whole:
                    ep_title = (title if not series else f"{title} (part {n_piece} of {len(picked)})"
                                if in_parts else episode_title(title, filename))
                else:
                    if not min_dur <= dur <= max_dur:
                        print(f"{tag} skip {ident}: duration {fmt(dur)} out of range")
                        continue
                    ep_title = episode_title(title, filename) if series else title
                    if series and any(w in ep_title.lower() for w in EXCLUDE_TITLE_WORDS):
                        print(f"{tag} skip {ident}: excluded episode '{ep_title[:50]}'")
                        continue
                    key = title_key(ep_title)
                    # Episodes only clash on an exact match: "Batman The Animated Series" would
                    # otherwise count as a copy of every episode whose title contains it.
                    if key and (key in seen if series else is_duplicate(key, seen)):
                        print(f"{tag} skip {ident}: duplicate of '{ep_title[:50]}'")
                        continue
                    seen.add(key)
                items.append({
                    "id": ident,
                    "title": ep_title,
                    "dur": round(dur, 2),
                    "url": DOWNLOAD_URL.format(id=ident, name=urllib.parse.quote(filename)),
                    "desc": desc,
                    "thumb": THUMB_URL.format(id=urllib.parse.quote(ident)),
                })
                total += dur
                print(f"{tag} + {ep_title[:60]} ({fmt(dur)})  channel total {fmt(total)}")
            if ident in include and not any(it["id"] == ident for it in items):
                print(f"{tag} ! must-include {ident} added nothing")
        except Exception as exc:
            print(f"{tag} ! {ident}: {exc}")
        finally:
            time.sleep(DELAY)

    if include:
        # Must-haves were fetched first; mix them into the lineup (each upload's
        # episodes stay together).
        groups = {}
        for it in items:
            groups.setdefault(it["id"], []).append(it)
        order = list(groups.values())
        rng.shuffle(order)
        items = [it for group in order for it in group]

    if game_of:
        # A game uploaded as "pt. 1", "pt. 2"... in separate items: play its parts back to back,
        # in order, where the first one landed in the shuffle.
        games = {}
        for it in items:
            games.setdefault(game_of[it["id"]][0], []).append(it)
        items = [it for group in games.values()
                 for it in sorted(group, key=lambda it: game_of[it["id"]][1])]

    if bumps and items:
        found = fetch_bumps(bumps, len(items), rng)
        if found:
            # Show, bump, show, bump... (bumps repeat if there are fewer than shows).
            items = [x for i, it in enumerate(items) for x in (it, found[i % len(found)])]
            total = sum(it["dur"] for it in items)

    print(f"  -> {len(items)} items, {fmt(total)}")
    return items


def load_existing():
    try:
        return {c["name"]: c for c in json.loads(OUT_PATH.read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def main():
    sys.stdout.reconfigure(errors="replace")  # odd titles must not crash a Windows console
    # Optional arguments: rebuild only these channels and keep the rest of catalog.json.
    only = set(sys.argv[1:])
    unknown = only - CHANNELS.keys()
    if unknown:
        print(f"Unknown channel(s): {', '.join(sorted(unknown))}")
        print(f"Choose from: {', '.join(CHANNELS)}")
        return 1
    existing = load_existing() if only else {}

    catalog = []
    for name, (query, desc, *opts) in CHANNELS.items():
        if only and name not in only:
            if name in existing:
                catalog.append({**existing[name], "desc": desc})
            continue
        items = build_channel(name, query, **(opts[0] if opts else {}))
        if items:
            catalog.append({"name": name, "desc": desc, "items": items})
        else:
            print(f"  ! '{name}' is empty and will be left out")

    if not catalog:
        print("\nNo channels built; catalog.json was not written.")
        return 1

    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"\nWrote {OUT_PATH} with {len(catalog)} channels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
