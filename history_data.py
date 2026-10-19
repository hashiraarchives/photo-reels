"""
History lens for AAP (owner, 2026-10): every video walks through time and
teaches a little on the way -- the era a photo belongs to, what Hollywood (and
America) was doing that year, and a through-line for themed shorts.

Facts here are deliberately the well-documented, uncontroversial ones (dates
of premieres, ceremonies, rulings). This audience lived much of it and corrects
mistakes in the comments, so nothing goes in that needs an argument to defend.
Keep every line short enough to read on a phone in a few seconds.
"""
import random
import re
from typing import Dict, List, Optional

# --- eras ----------------------------------------------------------------------
# Contiguous, non-overlapping year ranges. 'tag' is the small-caps label on
# the Shorts year ticker; 'title'/'lines' fill the long-form chapter card;
# 'desc' is the description's short-history paragraph.
ERAS: List[Dict] = [
    {'key': 'birth', 'name': "the birth of the movie star", 'lo': 1890, 'hi': 1919, 'title': 'The Birth of the Movie Star',
     'tag': 'THE BIRTH OF THE MOVIE STAR',
     'lines': ["Around 1910, studios began billing actors by name.",
               "Audiences now bought tickets to see faces they loved."],
     'desc': ("In the 1910s the film business moved west to Hollywood, and studios "
              "learned that audiences came back for the faces they loved. Mary Pickford "
              "became 'America's Sweetheart', and in 1919 she, Charlie Chaplin, Douglas "
              "Fairbanks and D.W. Griffith founded United Artists.")},
    {'key': 'silent', 'name': "the silent screen", 'lo': 1920, 'hi': 1926, 'title': 'The Silent Screen',
     'tag': 'THE ROARING TWENTIES',
     'lines': ["Movie palaces seating thousands opened across America.",
               "Bobbed hair and flapper style went from scandal to fashion."],
     'desc': ("The Roaring Twenties were the high point of silent film. Grand movie "
              "palaces opened in every big city, Rudolph Valentino became the screen's "
              "great lover in The Sheik (1921), and stars like Clara Bow and Louise "
              "Brooks set the flapper style the whole country copied.")},
    {'key': 'talkies', 'name': "the first talkies", 'lo': 1927, 'hi': 1933, 'title': 'The Talkies Arrive',
     'tag': 'THE TALKIES ARRIVE',
     'lines': ["October 1927: The Jazz Singer brought spoken dialogue to the movies.",
               "May 1929: the first Academy Awards were handed out."],
     'desc': ("The Jazz Singer (1927) brought synchronized dialogue to a feature film, "
              "and within a few years silent pictures were gone. The first Academy Awards "
              "were presented in May 1929, and in 1930 MGM sold Greta Garbo's first sound "
              "film with two words: 'Garbo Talks!'")},
    {'key': 'golden', 'name': "Hollywood's golden age", 'lo': 1934, 'hi': 1940, 'title': "Hollywood's Golden Age",
     'tag': "HOLLYWOOD'S GOLDEN AGE",
     'lines': ["Becky Sharp (1935) was the first feature in three-strip Technicolor.",
               "1939 is still called Hollywood's greatest year."],
     'desc': ("From 1934 the Production Code was strictly enforced, and the studios "
              "answered with glamour, wit and color: Becky Sharp (1935) was the first "
              "feature in three-strip Technicolor, and 1939 -- the year of Gone with the "
              "Wind and The Wizard of Oz -- is still called Hollywood's greatest year.")},
    {'key': 'war', 'name': "the war years", 'lo': 1941, 'hi': 1945, 'title': 'Hollywood Goes to War',
     'tag': 'HOLLYWOOD GOES TO WAR',
     'lines': ["Stars sold war bonds, toured with the USO and served in uniform.",
               "The Hollywood Canteen opened its doors to servicemen in 1942."],
     'desc': ("During the Second World War, Hollywood's stars sold war bonds, toured "
              "with the USO and served in uniform. The Hollywood Canteen opened in 1942, "
              "and Betty Grable's 1943 swimsuit photo became the most famous pinup of "
              "the war.")},
    {'key': 'postwar', 'name': "the postwar years", 'lo': 1946, 'hi': 1952, 'title': 'Postwar Hollywood',
     'tag': 'POSTWAR HOLLYWOOD',
     'lines': ["In 1946, American movie attendance hit its postwar peak.",
               "Then television began arriving in living rooms."],
     'desc': ("Movie attendance hit its postwar peak in 1946. Two years later the "
              "Paramount ruling began breaking up the studios' theater chains, and by the "
              "early 1950s television was arriving in American living rooms.")},
    {'key': 'widescreen', 'name': "the widescreen fifties", 'lo': 1953, 'hi': 1959, 'title': 'Widescreen and Technicolor',
     'tag': 'THE WIDESCREEN FIFTIES',
     'lines': ["CinemaScope arrived in 1953 with The Robe.",
               "Drive-in theaters peaked at over 4,000 screens."],
     'desc': ("Hollywood fought television with spectacle: CinemaScope arrived with "
              "The Robe (1953), drive-in theaters peaked at over 4,000 screens, and in "
              "1956 Grace Kelly left the movies to become Princess of Monaco.")},
    {'key': 'sixties', 'name': "the end of the studio era", 'lo': 1960, 'hi': 1979, 'title': 'The End of the Studio Era',
     'tag': 'THE END OF THE STUDIO ERA',
     'lines': ["Elizabeth Taylor signed for a record $1 million to play Cleopatra.",
               "In 1968 the rating system replaced the Production Code."],
     'desc': ("The old studio system wound down in the 1960s. Elizabeth Taylor signed "
              "for a record $1 million to play Cleopatra (1963), Audrey Hepburn's little "
              "black dress became a fashion icon, and in November 1968 the rating system "
              "replaced the Production Code.")},
]

# --- one-line "that year" context -----------------------------------------------
# Shown under a photo of the same year: "Clara Bow, 1927. That year, The Jazz
# Singer brought spoken dialogue to the movies." Phrased to complete the
# sentence "That year, ...".
YEAR_EVENTS: Dict[int, List[str]] = {
    1919: ["Pickford, Chaplin, Fairbanks and Griffith founded United Artists"],
    1921: ["Rudolph Valentino became a sensation in The Sheik"],
    1923: ["the Hollywoodland sign went up in the hills above Los Angeles"],
    1925: ["Ben-Hur became the most expensive silent film ever made"],
    1926: ["Don Juan premiered with a synchronized score and sound effects"],
    1927: ["The Jazz Singer brought spoken dialogue to the movies",
           "Clara Bow became the 'It Girl' in It"],
    1928: ["Mickey Mouse debuted in Steamboat Willie"],
    1929: ["the first Academy Awards were presented in Hollywood"],
    1930: ["Greta Garbo spoke her first lines on screen in Anna Christie"],
    1931: ["Dracula and Frankenstein started Universal's monster craze"],
    1932: ["Grand Hotel brought an all-star cast to the screen"],
    1933: ["King Kong climbed the Empire State Building"],
    1934: ["the Production Code began to be strictly enforced"],
    1935: ["Becky Sharp became the first feature in three-strip Technicolor"],
    1936: ["Chaplin said farewell to the Little Tramp in Modern Times"],
    1937: ["Disney's Snow White became America's first full-length animated feature"],
    1938: ["The Adventures of Robin Hood dazzled audiences in Technicolor"],
    1939: ["Gone with the Wind and The Wizard of Oz both premiered"],
    1940: ["The Philadelphia Story paired Katharine Hepburn, Cary Grant and James Stewart"],
    1941: ["Citizen Kane premiered"],
    1942: ["Casablanca premiered and the Hollywood Canteen opened its doors"],
    1943: ["Betty Grable posed for the most famous pinup photo of the war"],
    1944: ["Going My Way and Double Indemnity filled theaters"],
    1945: ["the war ended and Hollywood's stars came home"],
    1946: ["It's a Wonderful Life premiered",
           "American movie attendance hit its postwar peak"],
    1947: ["Miracle on 34th Street premiered"],
    1948: ["the Paramount ruling began breaking up the studios' theater chains"],
    1949: ["television's first Emmy Awards were presented"],
    1950: ["All About Eve and Sunset Boulevard both premiered"],
    1951: ["I Love Lucy debuted on CBS"],
    1952: ["Singin' in the Rain premiered"],
    1953: ["CinemaScope debuted with The Robe"],
    1954: ["Grace Kelly starred in Rear Window and The Country Girl"],
    1955: ["Disneyland opened in Anaheim, California"],
    1956: ["Grace Kelly married Prince Rainier and became Princess of Monaco"],
    1957: ["Elvis Presley starred in Jailhouse Rock"],
    1958: ["Hitchcock's Vertigo premiered"],
    1959: ["Ben-Hur and Some Like It Hot both premiered"],
    1960: ["Hitchcock's Psycho shocked audiences"],
    1961: ["Breakfast at Tiffany's premiered"],
    1962: ["Dr. No introduced James Bond to movie audiences"],
    1963: ["Cleopatra opened, the most expensive film made up to that time"],
    1964: ["My Fair Lady premiered"],
    1965: ["The Sound of Music became a box-office phenomenon"],
    1968: ["the rating system replaced the Production Code"],
    1969: ["Apollo 11 landed on the Moon"],
}


def era_for(year: Optional[int]) -> Optional[Dict]:
    if not year:
        return None
    for e in ERAS:
        if e['lo'] <= year <= e['hi']:
            return e
    return None


def era_by_key(key: str) -> Optional[Dict]:
    return next((e for e in ERAS if e['key'] == key), None)


def year_event(year: Optional[int], seed: int = 0) -> Optional[str]:
    ev = YEAR_EVENTS.get(year or 0)
    return ev[seed % len(ev)] if ev else None


_YEAR = re.compile(r'\b(18[89]\d|19[0-8]\d)\b')
_DECADE = re.compile(r'\b(19[0-7])0s\b')


def photo_year(clip: Dict, name: Optional[str] = None) -> Optional[int]:
    """The photo's year, read from (in order of trust) the Commons date field,
    the filename, the caption, then a film category ("Ben-Hur (1925 film)").
    A year impossible for the named star (aged under 16 or over 75) is skipped:
    archive filenames often carry a film's year, not the photo's."""
    import star_data as sd
    for field in ('date', 'filename', 'image_filename', 'caption',
                  'generated_caption', 'category', 'source_category'):
        m = _YEAR.search(str(clip.get(field) or ''))
        if m:
            y = int(m.group(1))
            if name and not sd.plausible_year(name, y):
                continue
            return y
    return None


def approx_year(clip: Dict, name: Optional[str] = None) -> Optional[int]:
    """photo_year, else a decade mid-point ("1940s" -> 1945), else the middle
    of a known star's career. For ORDERING only -- never shown on screen."""
    y = photo_year(clip, name)
    if y:
        return y
    for field in ('date', 'caption', 'generated_caption', 'filename', 'image_filename'):
        m = _DECADE.search(str(clip.get(field) or ''))
        if m:
            return int(m.group(1)) * 10 + 5
    if name:
        import star_data as sd
        info = sd.STAR_INFO.get(name.lower())
        if info:
            return info[1] + 28
    return None


# --- themed shorts -----------------------------------------------------------
# Each theme is a little story with a through-line. 'years' selects photos by
# their year; 'stars' (a predicate on the star's facts) selects by person. Every
# claim a theme's hook makes must hold for every photo it can pick: the Oscar
# theme only admits stars whose facts say they WON one.
def _oscar_winner(facts: List[str]) -> bool:
    return any(re.search(r'\bWon\b.*\bOscars?\b|Oscar winner', f) for f in facts)


def _nickname(facts: List[str]) -> Optional[str]:
    for f in facts:
        # a quoted name the star was known by -- not a quoted hairstyle
        if re.search(r"(?<=\s)'[^']+'", f) and 'hairstyle' not in f:
            return f
    return None


THEMES: List[Dict] = [
    {'key': 'talkies', 'years': (1926, 1933),
     'hook': "In 1927, the movies learned to talk.",
     'titles': ["When Hollywood Learned to Talk", "The Stars of the Early Talkies",
                "Hollywood's Leap From Silent to Sound"],
     'desc': ("In October 1927, The Jazz Singer brought spoken dialogue to the movies, "
              "and within three years the silent era was over. These are the faces of "
              "those few dizzy years, from the last silents to the first talkies."),
     'prompt': ("Silent or talkie?", "Which era wins")},
    {'key': 'silent', 'years': (1912, 1926), 'female': True,
     'hook': "Before the movies could talk, these faces said everything.",
     'titles': ["The Great Beauties of the Silent Screen", "Silent Film Stars in Rare Photos",
                "When the Movies Were Silent"],
     'desc': ("Before sound, a star had only her face, her eyes and the camera. These "
              "rare photographs come from the silent era, when Hollywood built the first "
              "movie stars and audiences fell in love without hearing a word."),
     'prompt': ("Could you watch a silent film?", "Tell us below")},
    {'key': 'golden', 'years': (1934, 1940),
     'hook': "1939 is still called Hollywood's greatest year.",
     'titles': ["Hollywood's Golden Age, 1934 to 1940", "The Glamour of Hollywood's Golden Age",
                "The Stars of Hollywood's Greatest Years"],
     'desc': ("The late 1930s were the studio system at its height: Technicolor, "
              "screwball comedy, great musicals and the stars who made them. 1939 alone "
              "gave us Gone with the Wind, The Wizard of Oz and Stagecoach."),
     'prompt': ("Best year for movies?", "Make your case below")},
    {'key': 'war', 'years': (1941, 1945),
     'hook': "1941 to 1945: Hollywood goes to war.",
     'titles': ["Hollywood Goes to War: The Stars of 1941 to 1945",
                "The Stars Who Kept America Smiling in WWII", "Hollywood During World War II"],
     'desc': ("During the Second World War, Hollywood's stars sold war bonds, toured with "
              "the USO and danced with servicemen at the Hollywood Canteen. These photos "
              "were taken between 1941 and 1945."),
     'prompt': ("Who did Dad have a pinup of?", "Tell us below")},
    {'key': 'fifties', 'years': (1950, 1959),
     'hook': "The 1950s: drive-ins, CinemaScope and movie-star glamour.",
     'titles': ["The Leading Ladies of the 1950s", "Hollywood Glamour in the 1950s",
                "1950s Hollywood in Rare Photos"],
     'desc': ("In the 1950s Hollywood fought television with spectacle: CinemaScope, "
              "Technicolor and stars who looked larger than life on a drive-in screen. "
              "Every photo here comes from that decade."),
     'prompt': ("Drive-in or movie palace?", "Tell us below")},
    {'key': 'nicknames', 'stars': _nickname,
     'hook': "Old Hollywood loved a nickname.",
     'titles': ["Old Hollywood's Famous Nicknames", "The It Girl, the Sweater Girl and More",
                "Hollywood Nicknames You Still Remember"],
     'desc': ("The 'It Girl', 'America's Sweetheart', the 'Sweater Girl': the studios' "
              "publicity departments gave their stars nicknames the whole country "
              "remembered. How many did you know?"),
     'prompt': ("Which nickname fits best?", "Tell us below")},
    {'key': 'oscars', 'stars': _oscar_winner,
     'hook': "Every star in this short won an Oscar.",
     'titles': ["Oscar Winners of Old Hollywood", "The Oscar-Winning Stars of the Golden Age",
                "They All Won an Oscar"],
     'desc': ("Every star in this short took home an Academy Award. The Oscars began in "
              "May 1929 with a ceremony that lasted about fifteen minutes; these are some "
              "of the faces that won them in the decades that followed."),
     'prompt': ("Who deserved more Oscars?", "Make your case below")},
]


# LIFE MOMENTS (owner, 2026-10, from the Golden Frame Hollywood study: their
# winners are real moments, one human theme per video). Public-domain only.
# 'rows' selects by the photo itself: 'couple' = names exactly one known
# actress and one known actor (screen couples), 'beach' = harvested by
# harvest_life.py into the life pool. '{span}' becomes " (1920s to 1940s)".
THEMES += [
    {'key': 'couples', 'rows': 'couple', 'life': True,
     'hook': "Hollywood's great screen couples.",
     'card': "Hollywood's Great Screen Couples",
     'titles': ["Hollywood's Great Screen Couples{span}",
                "Old Hollywood Love Stories: Golden Age Screen Couples{span}",
                "The Screen Couples Who Made Hollywood Swoon{span}"],
     'desc': ("Old Hollywood sold romance by the reel: the studios paired their biggest "
              "stars again and again, and audiences came back to watch them fall in love. "
              "A few of those pairs fell for each other off screen too."),
     'lines': ["The studios paired their biggest stars again and again.",
               "Audiences came back to watch them fall in love."],
     'prompt': ("Best screen couple ever?", "Make your case below")},
    {'key': 'beach', 'rows': 'beach', 'life': True,
     'hook': "Bathing beauties and beach days, the way they really were.",
     'card': "Bathing Beauties and Beach Days",
     'titles': ["Bathing Beauties and Beach Days{span}",
                "Vintage Beach Days in Rare Photos{span}",
                "Old-Time Bathing Beauties in Rare Photos{span}"],
     'desc': ("In the 1910s and 1920s Mack Sennett's Bathing Beauties made the beach a "
              "Hollywood fixture, and in the early 1920s some beaches still had officers "
              "checking that swimsuits were long enough. These are real photos from those summers."),
     'lines': ["Mack Sennett's Bathing Beauties made the beach a Hollywood fixture.",
               "Some beaches still had officers checking swimsuit lengths."],
     'prompt': ("Ever been to a boardwalk?", "Share a memory below")},
]


def theme_pools(theme: Dict):
    """Which pool CSVs a theme draws from."""
    import config
    if theme.get('rows') == 'beach':
        return (config.GOLDMINE_LIFE_CSV,)
    if theme.get('rows') == 'couple':
        return tuple(p for p in (config.GOLDMINE3_CSV, config.GOLDMINE_CSV, config.GOLDMINE2_CSV,
                                 getattr(config, 'GOLDMINE4_CSV', '')) if p)
    return (config.GOLDMINE3_CSV,)


def row_in_theme(theme: Dict, row: Dict) -> bool:
    """Row-level membership for the 'rows' themes (pool rows or clips)."""
    import star_data as sd
    fn = row.get('image_filename') or row.get('filename') or ''
    cat = row.get('source_category') or row.get('category') or ''
    if theme.get('rows') == 'beach':
        if (row.get('life_theme') or '') != 'beach':
            return False
        # "Bathing Beauties": a photo led by a man's name (a champion
        # swimmer, a comedian) doesn't keep the promise
        lead = ' '.join(((row.get('description') or '') or fn).split()[:2])
        return not sd.likely_male(lead) and not sd.likely_male(sd.identify(fn, cat) or '')
    if theme.get('rows') == 'couple':
        return sd.screen_couple(fn, cat) is not None
    return False


def theme_title(theme: Dict, k: int, years: List[int]) -> str:
    ys = [y for y in years if y]
    span = ''
    if ys:
        d0, d1 = (min(ys) // 10) * 10, (max(ys) // 10) * 10
        span = f" ({d0}s to {d1}s)" if d1 > d0 else f" ({d0}s)"
    t = theme['titles'][k % len(theme['titles'])]
    return t.replace('{span}', span)


def theme_by_key(key: str) -> Optional[Dict]:
    return next((t for t in THEMES if t['key'] == key), None)


def theme_admits(theme: Dict, name: Optional[str], year: Optional[int],
                 clip: Optional[Dict] = None) -> bool:
    """Whether a photo (its identified star and year) fits a theme's promise."""
    import star_data as sd
    if 'rows' in theme:
        return bool(clip) and row_in_theme(theme, clip)
    if 'years' in theme:
        lo, hi = theme['years']
        if not (year and lo <= year <= hi):
            return False
        if theme.get('female') and name and sd.star_gender(name) == 'm':
            return False
        return True
    if 'stars' in theme:
        return bool(name) and bool(theme['stars'](sd.facts_for(name)))
    return False


def theme_fact(theme: Dict, name: str) -> Optional[str]:
    """The fact a theme's caption should lead with for this star."""
    import star_data as sd
    facts = sd.facts_for(name)
    if theme['key'] == 'nicknames':
        return _nickname(facts)
    if theme['key'] == 'oscars':
        return next((f for f in facts if re.search(r'Oscar', f)), None)
    return None


def pick_theme(available: Dict[str, int], need: int, recent: List[str],
               rng: Optional[random.Random] = None) -> Optional[Dict]:
    """A theme with at least `need` candidate rows, avoiding recently used ones
    when possible. `available` maps theme key -> candidate row count."""
    rng = rng or random
    ok = [t for t in THEMES if available.get(t['key'], 0) >= need]
    fresh = [t for t in ok if t['key'] not in recent[-4:]]
    pool = fresh or ok
    return rng.choice(pool) if pool else None


def eras_in(years: List[int]) -> List[Dict]:
    """Eras covered by a list of years, in chronological order."""
    seen, out = set(), []
    for y in sorted(y for y in years if y):
        e = era_for(y)
        if e and e['key'] not in seen:
            seen.add(e['key'])
            out.append(e)
    return out
