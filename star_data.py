"""
Star facts, quotes and humor for Shorts packaging.

STAR_INFO  - gender + birth year. Gender picks the right wording ("her peak"
             vs "his peak": a template once shipped "This is Gary Cooper at her
             peak"). Birth year rejects impossible title years ("Marilyn Monroe
             in 1929" shipped when she was three).
QUOTES     - lines the star actually spoke, each with its source. Almost all
             are famous film dialogue, whose source is the film itself, so
             they can be checked. Widely repeated "quotes" with shaky
             provenance (much of what circulates under Marilyn Monroe's and
             Mae West's names) are deliberately absent: this audience knows
             these films, and a misattribution gets corrected in the comments
             and costs the channel its credibility.
HUMOR_*    - affectionate, never mocking. The audience is older US men; the
             joke is always on the era or on "us", never on the viewer's age.

Keep every quote under ~90 characters: it has to fit a phone screen in type an
older viewer can read at arm's length.
"""
from typing import Dict, List, Optional, Tuple

# name (lowercase) -> (gender 'f'/'m', birth year)
STAR_INFO: Dict[str, Tuple[str, int]] = {
    # --- leading ladies
    'marilyn monroe': ('f', 1926), 'audrey hepburn': ('f', 1929),
    'grace kelly': ('f', 1929), 'elizabeth taylor': ('f', 1932),
    'rita hayworth': ('f', 1918), 'ava gardner': ('f', 1922),
    'bette davis': ('f', 1908), 'joan crawford': ('f', 1904),
    'ginger rogers': ('f', 1911), 'katharine hepburn': ('f', 1907),
    'vivien leigh': ('f', 1913), 'ingrid bergman': ('f', 1915),
    'sophia loren': ('f', 1934), 'brigitte bardot': ('f', 1934),
    'lauren bacall': ('f', 1924), 'gene tierney': ('f', 1920),
    'veronica lake': ('f', 1922), 'lana turner': ('f', 1921),
    'dorothy lamour': ('f', 1914), 'hedy lamarr': ('f', 1914),
    'dolores del rio': ('f', 1904), 'dolores rio': ('f', 1904),
    'carole lombard': ('f', 1908), 'jean harlow': ('f', 1911),
    'mae west': ('f', 1893), 'barbara stanwyck': ('f', 1907),
    'claudette colbert': ('f', 1903), 'irene dunne': ('f', 1898),
    'myrna loy': ('f', 1905), 'raquel welch': ('f', 1940),
    'natalie wood': ('f', 1938), 'jane russell': ('f', 1921),
    'jayne mansfield': ('f', 1933), 'rita moreno': ('f', 1931),
    'kim novak': ('f', 1933), 'doris day': ('f', 1922),
    'judy garland': ('f', 1922), 'bettie page': ('f', 1923),
    'teresa wright': ('f', 1918), 'glenda farrell': ('f', 1904),
    'mary miles minter': ('f', 1902), 'bebe daniels': ('f', 1901),
    'greta garbo': ('f', 1905), 'marlene dietrich': ('f', 1901),
    'louise brooks': ('f', 1906), 'clara bow': ('f', 1905),
    'lillian gish': ('f', 1893), 'mary pickford': ('f', 1892),
    'betty grable': ('f', 1916), 'norma shearer': ('f', 1902),
    'gloria swanson': ('f', 1899), 'olivia de havilland': ('f', 1916),
    'joan fontaine': ('f', 1917), 'loretta young': ('f', 1913),
    'paulette goddard': ('f', 1910), 'ann sheridan': ('f', 1915),
    'susan hayward': ('f', 1917), 'esther williams': ('f', 1921),
    'cyd charisse': ('f', 1922), 'linda darnell': ('f', 1923),
    'jeanne crain': ('f', 1925), 'kay francis': ('f', 1905),
    'jean arthur': ('f', 1900), 'rosalind russell': ('f', 1907),
    'donna reed': ('f', 1921), 'deborah kerr': ('f', 1921),
    'janet leigh': ('f', 1927), 'anne baxter': ('f', 1923),
    "maureen o'hara": ('f', 1920), 'anita ekberg': ('f', 1931),
    'gina lollobrigida': ('f', 1927), 'debbie reynolds': ('f', 1932),
    'constance bennett': ('f', 1904), 'miriam hopkins': ('f', 1902),
    'sylvia sidney': ('f', 1910), 'alice faye': ('f', 1915),
    'betty hutton': ('f', 1921), 'eleanor powell': ('f', 1912),
    'joan bennett': ('f', 1910), 'shirley temple': ('f', 1928),
    'ann-margret': ('f', 1941), 'barbara eden': ('f', 1931),
    'tina louise': ('f', 1934), 'angie dickinson': ('f', 1931),
    'julie newmar': ('f', 1933), 'mamie van doren': ('f', 1931),
    'lucille ball': ('f', 1911), 'dorothy dandridge': ('f', 1922),
    'lena horne': ('f', 1917), 'fay wray': ('f', 1907),
    'anna may wong': ('f', 1905), 'theda bara': ('f', 1885),
    'colleen moore': ('f', 1899), 'pola negri': ('f', 1897),
    'marion davies': ('f', 1897), 'ida lupino': ('f', 1918),
    'merle oberon': ('f', 1911), 'gloria grahame': ('f', 1923),
    'jean simmons': ('f', 1929), 'eva marie saint': ('f', 1924),
    'joan collins': ('f', 1933), 'julie london': ('f', 1926),
    'shirley maclaine': ('f', 1934), 'yvonne de carlo': ('f', 1922),
    'virginia mayo': ('f', 1920), 'rhonda fleming': ('f', 1923),
    # --- leading men
    'cary grant': ('m', 1904), 'clark gable': ('m', 1901),
    'humphrey bogart': ('m', 1899), 'james dean': ('m', 1931),
    'gary cooper': ('m', 1901), 'errol flynn': ('m', 1909),
    'gregory peck': ('m', 1916), 'marlon brando': ('m', 1924),
    'james stewart': ('m', 1908), 'spencer tracy': ('m', 1900),
    'tyrone power': ('m', 1914), 'robert mitchum': ('m', 1917),
    'kirk douglas': ('m', 1916), 'burt lancaster': ('m', 1913),
    'rock hudson': ('m', 1925), 'paul newman': ('m', 1925),
    'frank sinatra': ('m', 1915), 'fred astaire': ('m', 1899),
    'gene kelly': ('m', 1912), 'steve mcqueen': ('m', 1930),
    'tony curtis': ('m', 1925), 'william holden': ('m', 1918),
    'henry fonda': ('m', 1905), 'alan ladd': ('m', 1913),
    'glenn ford': ('m', 1916), 'montgomery clift': ('m', 1920),
    'charlton heston': ('m', 1923), 'dean martin': ('m', 1917),
    'john wayne': ('m', 1907), 'buster keaton': ('m', 1895),
    'charlie chaplin': ('m', 1889), 'rudolph valentino': ('m', 1895),
    'douglas fairbanks': ('m', 1883), 'robert taylor': ('m', 1911),
    'gene autry': ('m', 1907), 'richard burton': ('m', 1925),
    'bing crosby': ('m', 1903), 'erich von stroheim': ('m', 1885),
    'lon chaney': ('m', 1883), 'robert wagner': ('m', 1930),
    'victor mature': ('m', 1913), 'randolph scott': ('m', 1898),
    'james garner': ('m', 1928), 'audie murphy': ('m', 1925),
}

# name (lowercase) -> [(quote, source)]. Film lines are attributed to the
# actor who spoke them; the source names the film so it can be checked.
QUOTES: Dict[str, List[Tuple[str, str]]] = {
    'mae west': [
        ("When I'm good, I'm very good. But when I'm bad, I'm better.", "I'm No Angel (1933)"),
        ("Why don't you come up sometime and see me?", "She Done Him Wrong (1933)"),
        ("It's not the men in my life that counts. It's the life in my men.", "I'm No Angel (1933)"),
    ],
    'bette davis': [
        ("Fasten your seatbelts. It's going to be a bumpy night.", "All About Eve (1950)"),
        ("What a dump!", "Beyond the Forest (1949)"),
    ],
    'greta garbo': [
        ("I want to be alone.", "Grand Hotel (1932)"),
    ],
    'humphrey bogart': [
        ("Here's looking at you, kid.", "Casablanca (1942)"),
        ("Of all the gin joints in all the towns in all the world, she walks into mine.", "Casablanca (1942)"),
        ("Louis, I think this is the beginning of a beautiful friendship.", "Casablanca (1942)"),
        ("The stuff that dreams are made of.", "The Maltese Falcon (1941)"),
    ],
    'ingrid bergman': [
        ("Play it, Sam. Play 'As Time Goes By.'", "Casablanca (1942)"),
        ("Kiss me. Kiss me as if it were the last time.", "Casablanca (1942)"),
    ],
    'lauren bacall': [
        ("You know how to whistle, don't you, Steve? You just put your lips together and blow.", "To Have and Have Not (1944)"),
    ],
    'clark gable': [
        ("Frankly, my dear, I don't give a damn.", "Gone with the Wind (1939)"),
        ("You should be kissed, and often, and by someone who knows how.", "Gone with the Wind (1939)"),
    ],
    'vivien leigh': [
        ("After all, tomorrow is another day!", "Gone with the Wind (1939)"),
        ("Fiddle-dee-dee!", "Gone with the Wind (1939)"),
    ],
    'gloria swanson': [
        ("All right, Mr. DeMille, I'm ready for my close-up.", "Sunset Boulevard (1950)"),
        ("I am big. It's the pictures that got small.", "Sunset Boulevard (1950)"),
        ("We didn't need dialogue. We had faces!", "Sunset Boulevard (1950)"),
    ],
    'marilyn monroe': [
        ("I always get the fuzzy end of the lollipop.", "Some Like It Hot (1959)"),
        ("Real diamonds! They must be worth their weight in gold!", "Some Like It Hot (1959)"),
        ("I can be smart when it's important, but most men don't like it.", "Gentlemen Prefer Blondes (1953)"),
    ],
    'marlon brando': [
        ("I coulda been a contender.", "On the Waterfront (1954)"),
        ("Stella!", "A Streetcar Named Desire (1951)"),
        ("I'm gonna make him an offer he can't refuse.", "The Godfather (1972)"),
    ],
    'rita hayworth': [
        ("If I'd been a ranch, they would've named me the Bar Nothing.", "Gilda (1946)"),
    ],
    'katharine hepburn': [
        ("The calla lilies are in bloom again.", "Stage Door (1937)"),
        ("The time to make up your mind about people is never.", "The Philadelphia Story (1940)"),
        ("Nature, Mr. Allnut, is what we are put in this world to rise above.", "The African Queen (1951)"),
    ],
    'cary grant': [
        ("Insanity runs in my family. It practically gallops.", "Arsenic and Old Lace (1944)"),
    ],
    'jean harlow': [
        ("Would you be shocked if I put on something more comfortable?", "Hell's Angels (1930)"),
    ],
    'judy garland': [
        ("Toto, I've a feeling we're not in Kansas anymore.", "The Wizard of Oz (1939)"),
        ("There's no place like home.", "The Wizard of Oz (1939)"),
    ],
    'audrey hepburn': [
        ("Rome. By all means, Rome.", "Roman Holiday (1953)"),
    ],
    'grace kelly': [
        ("Do you want a leg or a breast?", "To Catch a Thief (1955)"),
        ("Preview of coming attractions.", "Rear Window (1954)"),
    ],
    'gene kelly': [
        ("Dignity. Always dignity.", "Singin' in the Rain (1952)"),
    ],
    'gregory peck': [
        ("You never really understand a person until you consider things from his point of view.", "To Kill a Mockingbird (1962)"),
    ],
    'james stewart': [
        ("Well, for years I was smart. I recommend pleasant.", "Harvey (1950)"),
    ],
    'john wayne': [
        ("That'll be the day.", "The Searchers (1956)"),
    ],
    'marlene dietrich': [
        ("It took more than one man to change my name to Shanghai Lily.", "Shanghai Express (1932)"),
    ],
    'elizabeth taylor': [
        ("Maggie the Cat is alive! I'm alive!", "Cat on a Hot Tin Roof (1958)"),
    ],
    'james dean': [
        ("You're tearing me apart!", "Rebel Without a Cause (1955)"),
    ],
}

# Opening-frame hook captions. Short: they must read in under two seconds.
HUMOR_HOOKS_GENERIC = [
    "No filters. No Botox. No problem.",
    "Hollywood, before filters existed",
    "The original influencers",
    "Proof Grandpa had great taste",
    "Before streaming, there was THIS",
    "They don't make 'em like this anymore",
    "When a movie ticket cost a quarter",
    "Back when stars were STARS",
]
HUMOR_HOOKS_F = [
    "No filter needed. Ever.",
    "Admit it. You had a crush.",
    "Before Photoshop, there was her",
    "She didn't need a filter",
    "Grandpa's first crush",
]
HUMOR_HOOKS_M = [
    "Every guy wanted to be him",
    "Cooler than all of us",
    "Before Photoshop, there was him",
    "Style you can't buy anymore",
]


def _key(name: str) -> str:
    return (name or '').strip().lower()


def star_gender(name: str) -> Optional[str]:
    info = STAR_INFO.get(_key(name))
    return info[0] if info else None


def plausible_year(name: str, year: int) -> bool:
    """A photo year is believable for a star if they were 16-75 that year.
    Unknown stars pass (we can't judge), impossible years for known ones fail."""
    info = STAR_INFO.get(_key(name))
    if not info:
        return True
    return info[1] + 16 <= year <= info[1] + 75


def quotes_for(name: str) -> List[Tuple[str, str]]:
    return QUOTES.get(_key(name), [])


def pick_quote(name: str, seed: int) -> Optional[Tuple[str, str]]:
    q = quotes_for(name)
    return q[seed % len(q)] if q else None


def pick_hook(name: str, seed: int) -> str:
    """Humor hook for the opening frame. Star-specific wording only when we
    know the star's gender; otherwise the generic (star-free) set."""
    g = star_gender(name) if name else None
    if g == 'f':
        pool = HUMOR_HOOKS_F
        info = STAR_INFO[_key(name)]
        # "Admit it. You had a crush." only lands when the viewer could have:
        # a silent-era star was their grandfather's crush, not theirs.
        if info[1] < 1915:
            pool = [h for h in pool if 'You had a crush' not in h]
        else:
            pool = [h for h in pool if 'Grandpa' not in h]
    elif g == 'm':
        pool = HUMOR_HOOKS_M
    else:
        pool = HUMOR_HOOKS_GENERIC
    return pool[seed % len(pool)]


# --- per-photo wording for mixed shorts --------------------------------------
# One-liners shown mid-short, matched to the photo's era so the words FIT what
# is on screen. Short enough to read in a glance; affectionate, never mocking.
WIT_BY_ERA = {
    'silent': ["Silent films. Loud beauty.", "Before talkies, there was this face",
               "The Roaring Twenties, darling", "Flapper-era star power"],
    '1930s': ["1930s glamour hits different", "Hard times. Gorgeous movies.",
              "Pure 1930s class", "Old Hollywood at its finest"],
    '1940s': ["The pinup era, baby", "1940s glamour. No filter.",
              "Forties style, perfected", "Big bands. Bigger stars."],
    '1950s': ["Drive-in era royalty", "Peak 1950s Hollywood",
              "Saturday matinee material", "Chrome, fins and movie stars"],
    '1960s': ["Swinging Sixties style", "The '60s had it all",
              "Cool before cool had a name"],
}
WIT_ANY = ["Now THAT's a movie star", "Class never goes out of style",
           "The camera loved this face", "No stylist could fake this",
           "Worth the price of a ticket", "Hollywood royalty",
           "Pure old Hollywood"]
WIT_F = ["Hollywood's sweetheart", "Every man's pinup", "Grace you can't teach"]
WIT_M = ["Leading man energy", "Suave doesn't cover it", "They broke the mold"]

# Display names where str.title() gets it wrong.
DISPLAY = {"maureen o'hara": "Maureen O'Hara", 'ann-margret': 'Ann-Margret',
           'dolores del rio': 'Dolores del Rio', 'dolores rio': 'Dolores del Rio',
           'mamie van doren': 'Mamie Van Doren', 'olivia de havilland': 'Olivia de Havilland',
           'yvonne de carlo': 'Yvonne De Carlo', 'erich von stroheim': 'Erich von Stroheim',
           'shirley maclaine': 'Shirley MacLaine', 'steve mcqueen': 'Steve McQueen'}
_ALIASES = {'dolores rio': 'dolores del rio'}


def display_name(key: str) -> str:
    k = _key(key)
    return DISPLAY.get(k) or ' '.join(w.capitalize() for w in k.split())


def identify(*texts) -> Optional[str]:
    """The one known star a photo's filename/category/caption names, or None
    when it names nobody we know OR more than one person (a co-star still
    must not be labelled with the wrong name). Matches "Greta Garbo" and
    reversed archive names like "Garbo, Greta" (first AND last name as
    words; a surname alone -- Davis, Day, Grant, West -- is far too common)."""
    import re
    blob = re.sub(r'[_\-,./()]', ' ', ' '.join(t or '' for t in texts).lower())
    words = set(blob.split())
    found = set()
    for k in STAR_INFO:
        parts = k.replace('-', ' ').split()
        if k in blob or (len(parts) >= 2 and parts[0] in words and parts[-1] in words):
            found.add(_ALIASES.get(k, k))
    return display_name(found.pop()) if len(found) == 1 else None


def era_of(year: Optional[int]) -> Optional[str]:
    if not year:
        return None
    if year < 1930:
        return 'silent'
    return f"{(min(year, 1969) // 10) * 10}s"


def wit_options(name: Optional[str], year: Optional[int]):
    """Candidate one-liners for one photo, most fitting first."""
    opts = list(WIT_BY_ERA.get(era_of(year) or '', []))
    g = star_gender(name) if name else None
    opts += WIT_F if g == 'f' else WIT_M if g == 'm' else []
    return opts + WIT_ANY


# --- light details for the formal montage captions --------------------------
# The channel's best shorts (Jul-Sep 2025, 1.6k-4.8k views) captioned every
# photo with one calm, factual line: "Ella Raines with Poochie, 1945. Starred
# in 17 films, including Phantom Lady (1944)". These are the same kind of
# line: a signature film, an award or a well-known nickname, nothing that
# needs a citation argument.
STAR_FACTS = {
    'marilyn monroe': ["Star of Gentlemen Prefer Blondes (1953)", "Starred in Some Like It Hot (1959)"],
    'audrey hepburn': ["Won the Best Actress Oscar for Roman Holiday (1953)", "Holly Golightly in Breakfast at Tiffany's (1961)"],
    'grace kelly': ["Became Princess of Monaco in 1956", "Won the Best Actress Oscar for The Country Girl (1954)"],
    'elizabeth taylor': ["Two-time Best Actress Oscar winner", "Starred as Cleopatra (1963)"],
    'rita hayworth': ["Hollywood's 'Love Goddess'", "Unforgettable in Gilda (1946)"],
    'ava gardner': ["Breakout role in The Killers (1946)", "Starred in Mogambo (1953)"],
    'bette davis': ["Two-time Best Actress Oscar winner", "Starred in All About Eve (1950)"],
    'joan crawford': ["Won the Best Actress Oscar for Mildred Pierce (1945)"],
    'ginger rogers': ["Fred Astaire's most famous dance partner", "Won the Best Actress Oscar for Kitty Foyle (1940)"],
    'katharine hepburn': ["Won a record four Best Actress Oscars"],
    'vivien leigh': ["Scarlett O'Hara in Gone with the Wind (1939)", "Two-time Best Actress Oscar winner"],
    'ingrid bergman': ["Ilsa in Casablanca (1942)", "Three-time Oscar winner"],
    'sophia loren': ["Won an Oscar for Two Women (1960)"],
    'brigitte bardot': ["A sensation in And God Created Woman (1956)"],
    'lauren bacall': ["Famous for 'The Look'", "Debuted opposite Bogart in To Have and Have Not (1944)"],
    'gene tierney': ["Starred in Laura (1944)"],
    'veronica lake': ["Famous for her 'peekaboo' hairstyle", "Starred in Sullivan's Travels (1941)"],
    'lana turner': ["Hollywood's 'Sweater Girl'", "Starred in The Postman Always Rings Twice (1946)"],
    'dorothy lamour': ["Famous for her sarong in The Jungle Princess (1936)", "Co-starred in the Road films with Hope and Crosby"],
    'hedy lamarr': ["Co-invented frequency-hopping radio technology (1942)", "Starred in Samson and Delilah (1949)"],
    'carole lombard': ["Queen of the screwball comedy", "Starred in My Man Godfrey (1936)"],
    'jean harlow': ["Hollywood's original 'Blonde Bombshell'", "Starred in Red Dust (1932)"],
    'mae west': ["Starred in She Done Him Wrong (1933)"],
    'barbara stanwyck': ["Starred in Double Indemnity (1944)"],
    'claudette colbert': ["Won the Best Actress Oscar for It Happened One Night (1934)"],
    'irene dunne': ["Starred in The Awful Truth (1937)"],
    'myrna loy': ["Nora Charles in The Thin Man (1934)"],
    'natalie wood': ["Starred in West Side Story (1961)", "Starred in Rebel Without a Cause (1955)"],
    'jane russell': ["Starred in The Outlaw (1943)", "Co-starred with Marilyn in Gentlemen Prefer Blondes (1953)"],
    'jayne mansfield': ["Starred in The Girl Can't Help It (1956)"],
    'rita moreno': ["Won an Oscar for West Side Story (1961)"],
    'kim novak': ["Starred in Hitchcock's Vertigo (1958)"],
    'doris day': ["Starred in Pillow Talk (1959)"],
    'judy garland': ["Dorothy in The Wizard of Oz (1939)"],
    'bettie page': ["The 1950s 'Queen of Pinups'"],
    'teresa wright': ["Won an Oscar for Mrs. Miniver (1942)"],
    'glenda farrell': ["Played reporter Torchy Blane in the 1930s"],
    'bebe daniels': ["Silent star who later headlined 42nd Street (1933)"],
    'greta garbo': ["MGM's legendary Swedish star", "Starred in Ninotchka (1939)"],
    'marlene dietrich': ["Starred in The Blue Angel (1930)"],
    'louise brooks': ["Famous for her bob in Pandora's Box (1929)"],
    'clara bow': ["Hollywood's original 'It Girl'"],
    'lillian gish': ["The 'First Lady of American Cinema'", "Starred in Broken Blossoms (1919)"],
    'mary pickford': ["Known as 'America's Sweetheart'", "Co-founded United Artists (1919)"],
    'betty grable': ["Her swimsuit photo was WWII's most famous pinup"],
    'norma shearer': ["Won the Best Actress Oscar for The Divorcee (1930)"],
    'gloria swanson': ["Norma Desmond in Sunset Boulevard (1950)"],
    'olivia de havilland': ["Melanie in Gone with the Wind (1939)", "Two-time Best Actress Oscar winner"],
    'joan fontaine': ["Won the Best Actress Oscar for Suspicion (1941)"],
    'loretta young': ["Won the Best Actress Oscar for The Farmer's Daughter (1947)"],
    'paulette goddard': ["Starred with Chaplin in Modern Times (1936)"],
    'ann sheridan': ["Hollywood's 'Oomph Girl'"],
    'susan hayward': ["Won the Best Actress Oscar for I Want to Live! (1958)"],
    'esther williams': ["Star of Million Dollar Mermaid (1952)"],
    'cyd charisse': ["Danced with Gene Kelly in Singin' in the Rain (1952)"],
    'linda darnell': ["Starred in Forever Amber (1947)"],
    'jeanne crain': ["Starred in State Fair (1945)"],
    'kay francis': ["Starred in Trouble in Paradise (1932)"],
    'jean arthur': ["Starred in Mr. Smith Goes to Washington (1939)"],
    'rosalind russell': ["Starred in His Girl Friday (1940)"],
    'donna reed': ["Mary Bailey in It's a Wonderful Life (1946)"],
    'deborah kerr': ["Starred in From Here to Eternity (1953)", "Anna in The King and I (1956)"],
    'janet leigh': ["Starred in Hitchcock's Psycho (1960)"],
    'anne baxter': ["Eve in All About Eve (1950)"],
    "maureen o'hara": ["Starred in The Quiet Man (1952)", "Hollywood's 'Queen of Technicolor'"],
    'anita ekberg': ["The Trevi Fountain scene in La Dolce Vita (1960)"],
    'gina lollobrigida': ["Italian star of Trapeze (1956)"],
    'debbie reynolds': ["Starred in Singin' in the Rain (1952)"],
    'constance bennett': ["Starred in Topper (1937)"],
    'miriam hopkins': ["Starred in Trouble in Paradise (1932)"],
    'sylvia sidney': ["Starred in Fury (1936)"],
    'alice faye': ["Top musical star at 20th Century Fox"],
    'betty hutton': ["Starred in Annie Get Your Gun (1950)"],
    'eleanor powell': ["Tap-dancing star of Broadway Melody of 1940"],
    'joan bennett': ["Starred in Scarlet Street (1945)"],
    'dolores del rio': ["One of Hollywood's first Latin American stars"],
    'ann-margret': ["Starred with Elvis in Viva Las Vegas (1964)"],
    'barbara eden': ["Starred in I Dream of Jeannie (1965-70)"],
    'tina louise': ["Ginger on Gilligan's Island (1964-67)"],
    'angie dickinson': ["Starred in Rio Bravo (1959)"],
    'julie newmar': ["Catwoman in the 1960s Batman series"],
    'raquel welch': ["Starred in One Million Years B.C. (1966)"],
    'lucille ball': ["Starred in I Love Lucy (1951-57)"],
    'dorothy dandridge': ["First Black woman nominated for Best Actress, Carmen Jones (1954)"],
    'lena horne': ["Starred in Stormy Weather (1943)"],
    'fay wray': ["Starred in King Kong (1933)"],
    'anna may wong': ["Hollywood's first Chinese American star", "Starred in Shanghai Express (1932)"],
    'theda bara': ["Silent cinema's original 'Vamp'"],
    'colleen moore': ["The flapper star of Flaming Youth (1923)"],
    'marion davies': ["Silent comedy star of Show People (1928)"],
    'ida lupino': ["Actress and pioneering film director"],
    'merle oberon': ["Starred in Wuthering Heights (1939)"],
    'gloria grahame': ["Won an Oscar for The Bad and the Beautiful (1952)"],
    'jean simmons': ["Starred in Guys and Dolls (1955)"],
    'eva marie saint': ["Won an Oscar for On the Waterfront (1954)"],
    'yvonne de carlo': ["Lily in The Munsters (1964-66)"],
    'virginia mayo': ["Starred in The Best Years of Our Lives (1946)"],
    'rhonda fleming': ["Starred in Gunfight at the O.K. Corral (1957)"],
    'mamie van doren': ["1950s blonde star of Untamed Youth (1957)"],
    'shirley maclaine': ["Won an Oscar for Terms of Endearment (1983)"],
    'cary grant': ["Starred in North by Northwest (1959)"],
    'clark gable': ["Rhett Butler in Gone with the Wind (1939)", "Won an Oscar for It Happened One Night (1934)"],
    'humphrey bogart': ["Rick in Casablanca (1942)", "Won an Oscar for The African Queen (1951)"],
    'james dean': ["Starred in Rebel Without a Cause (1955)"],
    'gary cooper': ["Won Oscars for Sergeant York and High Noon"],
    'errol flynn': ["Starred in The Adventures of Robin Hood (1938)"],
    'gregory peck': ["Won an Oscar as Atticus Finch (1962)"],
    'marlon brando': ["Won Oscars for On the Waterfront and The Godfather"],
    'james stewart': ["Starred in It's a Wonderful Life (1946)", "Flew bombing missions in WWII"],
    'spencer tracy': ["Won back-to-back Best Actor Oscars (1937, 1938)"],
    'tyrone power': ["Starred in The Mark of Zorro (1940)"],
    'robert mitchum': ["Starred in The Night of the Hunter (1955)"],
    'kirk douglas': ["Starred in Spartacus (1960)"],
    'burt lancaster': ["Starred in From Here to Eternity (1953)"],
    'rock hudson': ["Starred with Doris Day in Pillow Talk (1959)"],
    'paul newman': ["Starred in Butch Cassidy and the Sundance Kid (1969)"],
    'frank sinatra': ["Won an Oscar for From Here to Eternity (1953)"],
    'fred astaire': ["Danced with Ginger Rogers in Top Hat (1935)"],
    'gene kelly': ["Starred in Singin' in the Rain (1952)"],
    'steve mcqueen': ["Starred in The Great Escape (1963)"],
    'tony curtis': ["Starred in Some Like It Hot (1959)"],
    'william holden': ["Won an Oscar for Stalag 17 (1953)"],
    'henry fonda': ["Starred in The Grapes of Wrath (1940)"],
    'alan ladd': ["Starred in Shane (1953)"],
    'glenn ford': ["Starred opposite Rita Hayworth in Gilda (1946)"],
    'montgomery clift': ["Starred in A Place in the Sun (1951)"],
    'charlton heston': ["Won an Oscar for Ben-Hur (1959)"],
    'dean martin': ["Rat Pack member and star of Rio Bravo (1959)"],
    'john wayne': ["Won an Oscar for True Grit (1969)"],
    'buster keaton': ["Silent comedy genius of The General (1926)"],
    'charlie chaplin': ["Created the Little Tramp"],
    'rudolph valentino': ["The silent era's 'Latin Lover', star of The Sheik (1921)"],
    'douglas fairbanks': ["Co-founded United Artists (1919)"],
    'robert taylor': ["Starred in Quo Vadis (1951)"],
    'bing crosby': ["Won an Oscar for Going My Way (1944)"],
    'richard burton': ["Starred in Cleopatra (1963)"],
    'victor mature': ["Starred in Samson and Delilah (1949)"],
    'randolph scott': ["Western star of Ride the High Country (1962)"],
    'james garner': ["Starred in Maverick (1957-62)"],
    'audie murphy': ["Decorated WWII hero turned film star"],
    'lon chaney': ["Starred in The Phantom of the Opera (1925)"],
    'erich von stroheim': ["Directed the silent epic Greed (1924)"],
    'gene autry': ["Hollywood's 'Singing Cowboy'"],
}


def facts_for(name: str):
    return STAR_FACTS.get(_ALIASES.get(_key(name), _key(name)), [])


import re as _re
_JUNK = _re.compile(r'\.(jpe?g|png|tiff?|webp)|_|file:|sayre|\d{5,}|nrfpt|annex', _re.I)


def montage_caption(name, year, raw_caption: str = '', seed: int = 0, quote=None) -> str:
    """One formal caption for a photo, in the house style of the channel's
    best shorts: "Rita Hayworth, 1946. Hollywood's 'Love Goddess'."
    A quote (text, source) replaces the fact when given. Returns '' when we
    can't say anything reliable about the photo."""
    if name:
        head = f"{name}, {year}." if year else f"{name}."
        if quote:
            src = _re.sub(r'\s*\((\d{4})\)$', r', \1', quote[1])
            return f"{head} “{quote[0].rstrip()}” ({src})"
        facts = facts_for(name)
        return f"{head} {facts[seed % len(facts)]}." if facts else head
    # Unnamed photo: archive captions are messy ("Dorothy Dalton Who's Who on
    # the Screen corp (1920)"), so keep only a leading person's name and a
    # year -- "Dorothy Dalton, 1920." -- or say nothing.
    raw = (raw_caption or '').strip()
    m = _re.match(r"([A-Z][a-z'\-]+(?:\s(?:de|del|van|von|la|le)?\s?[A-Z][a-z'\-]+){1,2})", raw)
    y = _re.search(r'\b(18[89]\d|19[0-8]\d)\b', raw)
    if not (m and y) or _JUNK.search(raw):
        return ''
    words = m.group(1).split()
    while words and words[-1].rstrip("'s") in _NOT_A_NAME:
        words.pop()
    if len(words) < 2 or any(w in _NOT_A_NAME for w in words):
        return ''
    return f"{' '.join(words)}, {y.group(1)}."


_NOT_A_NAME = {
    'Who', "Who's", 'Portrait', 'Publicity', 'Photo', 'Photograph', 'Studio',
    'Studios', 'Pictures', 'Picture', 'Company', 'Corporation', 'Theatre',
    'Theater', 'Film', 'Films', 'Hotel', 'Street', 'Avenue', 'Hollywood',
    'California', 'Magazine', 'Screen', 'Movie', 'Movies', 'Productions',
    'Warner', 'Paramount', 'Universal', 'Columbia', 'Metro', 'In', 'On', 'The',
    'At', 'And', 'With', 'From', 'For', 'Of', 'A', 'An', 'New', 'York', 'Los',
    'Angeles', 'Scene', 'Still', 'Actress', 'Actor', 'Miss', 'Mrs', 'Mr',
}
