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
import re
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

# 2026-10: more of the pool's faces. Recognising the MEN matters as much as the
# women: an unrecognised Ronald Colman fronted a short titled "Most Beautiful
# Actresses...". Recognising more silent-era women gives their photos a proper
# "Name, year." caption instead of raw archive text.
STAR_INFO.update({
    'ronald colman': ('m', 1891), 'john gilbert': ('m', 1897), 'ramon novarro': ('m', 1899),
    'wallace reid': ('m', 1891), 'harold lloyd': ('m', 1893), 'william powell': ('m', 1892),
    'fredric march': ('m', 1897), 'leslie howard': ('m', 1893), 'robert donat': ('m', 1905),
    'joel mccrea': ('m', 1905), 'ray milland': ('m', 1907), 'dick powell': ('m', 1904),
    'george raft': ('m', 1901), 'james cagney': ('m', 1899), 'edward g. robinson': ('m', 1893),
    'paul muni': ('m', 1895), 'laurence olivier': ('m', 1907), 'orson welles': ('m', 1915),
    'robert montgomery': ('m', 1904), 'melvyn douglas': ('m', 1901), 'franchot tone': ('m', 1905),
    'don ameche': ('m', 1908), 'dana andrews': ('m', 1909), 'cornel wilde': ('m', 1912),
    'john garfield': ('m', 1913), 'van johnson': ('m', 1916), 'tom mix': ('m', 1880),
    'william s. hart': ('m', 1864), 'john barrymore': ('m', 1882), 'lionel barrymore': ('m', 1878),
    'adolphe menjou': ('m', 1890), 'maurice chevalier': ('m', 1888), 'charles boyer': ('m', 1899),
    'cesar romero': ('m', 1907), 'gilbert roland': ('m', 1905), 'mickey rooney': ('m', 1920),
    'elvis presley': ('m', 1935), 'yul brynner': ('m', 1920), 'sean connery': ('m', 1930),
    'rex harrison': ('m', 1908), 'david niven': ('m', 1910), 'peter lawford': ('m', 1923),
    'jack lemmon': ('m', 1925), 'walter pidgeon': ('m', 1897), 'ronald reagan': ('m', 1911),
    'bob hope': ('m', 1903), 'groucho marx': ('m', 1890), 'lew ayres': ('m', 1908),
    'nelson eddy': ('m', 1901), 'john payne': ('m', 1912), 'robert ryan': ('m', 1909),
    'richard widmark': ('m', 1914), 'conrad nagel': ('m', 1897), 'antonio moreno': ('m', 1887),
    'richard barthelmess': ('m', 1895), 'william haines': ('m', 1900), 'rod la rocque': ('m', 1898),
    'thomas meighan': ('m', 1879), 'milton sills': ('m', 1882), 'warner baxter': ('m', 1889),
    'clive brook': ('m', 1887), 'herbert marshall': ('m', 1890), 'george brent': ('m', 1904),
    "pat o'brien": ('m', 1899), 'basil rathbone': ('m', 1892), 'boris karloff': ('m', 1887),
    'bela lugosi': ('m', 1882), 'claude rains': ('m', 1889), 'peter lorre': ('m', 1904),
    'jack holt': ('m', 1888), 'norman kerry': ('m', 1894), 'john boles': ('m', 1895),
    # silent-era and studio-era women the pool holds many photos of
    'norma talmadge': ('f', 1894), 'constance talmadge': ('f', 1898), 'mae murray': ('f', 1885),
    'mabel normand': ('f', 1892), 'billie dove': ('f', 1903), 'corinne griffith': ('f', 1894),
    'nita naldi': ('f', 1894), 'alice terry': ('f', 1899), 'lila lee': ('f', 1901),
    'agnes ayres': ('f', 1898), 'leatrice joy': ('f', 1893), 'mary astor': ('f', 1906),
    'joan blondell': ('f', 1906), 'jeanette macdonald': ('f', 1903), 'ruby keeler': ('f', 1909),
    'ann harding': ('f', 1902), 'nancy carroll': ('f', 1903), 'madge bellamy': ('f', 1899),
    'esther ralston': ('f', 1902), 'dorothy mackaill': ('f', 1903), 'vilma banky': ('f', 1901),
    'dolores costello': ('f', 1903), 'lupe velez': ('f', 1908), 'betty compson': ('f', 1897),
    'bessie love': ('f', 1898), 'frances farmer': ('f', 1913), 'ann miller': ('f', 1923),
    'june allyson': ('f', 1917), 'lizabeth scott': ('f', 1922), 'arlene dahl': ('f', 1925),
    'carole landis': ('f', 1919), 'evelyn keyes': ('f', 1916), 'gail russell': ('f', 1924),
    'jane wyman': ('f', 1917), 'ella raines': ('f', 1920), 'marie prevost': ('f', 1896),
    'phyllis haver': ('f', 1899), 'dorothy dalton': ('f', 1893), 'mary brian': ('f', 1906),
    'thelma todd': ('f', 1906), 'clara kimball young': ('f', 1890), 'anita stewart': ('f', 1895),
    'blanche sweet': ('f', 1896), 'mae marsh': ('f', 1894), 'dorothy gish': ('f', 1898),
    'pearl white': ('f', 1889), 'alla nazimova': ('f', 1879), 'viola dana': ('f', 1897),
    'edna purviance': ('f', 1895), 'olive thomas': ('f', 1894), 'marguerite clark': ('f', 1883),
    'florence lawrence': ('f', 1886), 'lois wilson': ('f', 1894), 'jacqueline logan': ('f', 1904),
    'lili damita': ('f', 1904), 'ann dvorak': ('f', 1911), 'virginia bruce': ('f', 1910),
    'frances dee': ('f', 1909), 'gloria stuart': ('f', 1910), 'anita page': ('f', 1910),
    'marsha hunt': ('f', 1917), 'vera-ellen': ('f', 1921), 'piper laurie': ('f', 1932),
    'toby wing': ('f', 1915), 'joan leslie': ('f', 1925), 'jean parker': ('f', 1915),
})

# Common men's first names, for people the tables above don't know: a caption
# naming "Wallace Beery" or "Ronald ..." means a man is on screen, whatever the
# STAR_INFO coverage.
_MALE_FIRST = {
    'john', 'william', 'james', 'robert', 'charles', 'george', 'richard', 'ronald',
    'douglas', 'harold', 'wallace', 'ramon', 'rudolph', 'lon', 'tom', 'buster', 'jack',
    'joseph', 'edward', 'frank', 'henry', 'thomas', 'walter', 'harry', 'fred', 'paul',
    'peter', 'david', 'michael', 'arthur', 'albert', 'louis', 'ralph', 'howard', 'clark',
    'cary', 'gary', 'errol', 'gregory', 'marlon', 'spencer', 'tyrone', 'kirk', 'burt',
    'rock', 'gene', 'steve', 'tony', 'alan', 'glenn', 'montgomery', 'charlton', 'dean',
    'bing', 'erich', 'victor', 'randolph', 'audie', 'humphrey', 'fredric',
    'joel', 'ray', 'dick', 'edmund', 'lionel', 'adolphe', 'maurice', 'cesar', 'gilbert',
    'mickey', 'elvis', 'yul', 'sean', 'rex', 'van', 'cornel', 'orson', 'laurence',
    'melvyn', 'franchot', 'don', 'milton', 'warner', 'clive', 'herbert', 'basil', 'boris',
    'bela', 'claude', 'conrad', 'antonio', 'norman', 'rod', 'lew', 'nelson', 'warren',
    'wallace', 'william', 'hobart', 'monte', 'ricardo', 'noah', 'lloyd', 'eddie', 'bert',
    'johnny', 'billy', 'jimmy', 'bobby', 'tommy', 'duke', 'buddy', 'jack',
}


_FEMALE_FIRST = {
    'mary', 'helen', 'margaret', 'dorothy', 'ruth', 'anna', 'elizabeth', 'mildred', 'frances',
    'marie', 'alice', 'florence', 'evelyn', 'lillian', 'gladys', 'edna', 'ethel', 'grace',
    'rose', 'irene', 'louise', 'clara', 'gloria', 'betty', 'jean', 'joan', 'lois', 'doris',
    'virginia', 'marion', 'martha', 'ann', 'anne', 'anita', 'bebe', 'billie', 'blanche',
    'carole', 'claudette', 'colleen', 'constance', 'corinne', 'daisy', 'dolores', 'edith',
    'eleanor', 'estelle', 'esther', 'fay', 'gail', 'greta', 'hedy', 'ida', 'janet', 'jane',
    'jeanette', 'jeanne', 'joyce', 'june', 'kay', 'laura', 'lauren', 'leatrice', 'lila',
    'lili', 'linda', 'loretta', 'lucille', 'lupe', 'mabel', 'madge', 'mae', 'marguerite',
    'marilyn', 'marjorie', 'marlene', 'maureen', 'merle', 'miriam', 'myrna', 'nancy',
    'natalie', 'nita', 'norma', 'olive', 'olivia', 'paulette', 'pearl', 'phyllis', 'pola',
    'priscilla', 'rita', 'rosalind', 'ruby', 'sally', 'shirley', 'sue', 'susan', 'sylvia',
    'thelma', 'theda', 'vera', 'veronica', 'viola', 'vivian', 'vivien', 'wanda', 'zasu',
    'barbara', 'bessie', 'catherine', 'charlotte', 'claire', 'eva', 'eve', 'harriet',
    'josephine', 'julia', 'julie', 'katharine', 'katherine', 'kathryn', 'lana', 'lena',
    'leila', 'lucy', 'mona', 'nora', 'patricia', 'peggy', 'ramona', 'renee', 'rosemary',
    'sarah', 'sophia', 'tallulah', 'vilma', 'winifred', 'ava', 'audrey', 'bette', 'debbie',
    'deborah', 'diana', 'donna', 'ella', 'elsa', 'gina', 'ginger', 'hazel', 'hilda',
    'jayne', 'judy', 'kim', 'lizabeth', 'marian', 'maria', 'marsha', 'mitzi', 'muriel',
    'olga', 'rhonda', 'rochelle', 'toby', 'yvonne', 'agnes', 'alma', 'alla', 'carmel',
    'carmen', 'cyd', 'gertrude', 'jacqueline', 'lottie', 'madeline', 'may', 'pauline',
    'mamie', 'jeanette', 'hope', 'joanne', 'lillie', 'minnie', 'nell', 'texas', 'zita',
}


def looks_like_person(name: str) -> bool:
    """True when a parsed 'name' starts with a real first name. Archive
    captions often lead with a FILM title -- "My Man Godfrey", "Her Soul's
    Inspiration", "Brother Rat" -- which must not be captioned as a person."""
    first = (name or '').strip().split(' ')[0].lower()
    return first in _MALE_FIRST or first in _FEMALE_FIRST


def likely_male(name: Optional[str]) -> bool:
    """True when a name is a known man, or starts with a common man's first name."""
    if not name:
        return False
    g = star_gender(name)
    if g:
        return g == 'm'
    first = name.strip().split()[0].lower() if name.strip() else ''
    return first in _MALE_FIRST


# Childhood photos of later stars ("Jean Harlow (taken at age 3)", "Baby
# Gumm"). Never in a short tagged for glamour, never captioned with an adult
# star's nickname -- a brand-safety line, not a style choice.
_CHILD_RE = None
_CHILD_STARS = {'shirley temple'}


def is_child_photo(text: str, name: Optional[str] = None, year: Optional[int] = None) -> bool:
    import re
    global _CHILD_RE
    if _CHILD_RE is None:
        _CHILD_RE = re.compile(
            r"\b(?:taken )?at (?:the )?age (?:of )?(?:[1-9]|1[0-5])\b|\baged? (?:[1-9]|1[0-5])\b|"
            r"(?<!bringing up )(?<!and a )\bbaby\b(?! face| doll| jane| mine)|\bas an? (?:child|baby|toddler|girl|boy)\b|\bchildhood\b|"
            r"\btoddler\b|\binfant\b|\b(?:[1-9]|1[0-5])[- ]years?[- ]old\b", re.I)
    if _CHILD_RE.search(text or ''):
        return True
    # Stars whose public-domain photos are overwhelmingly from childhood:
    # without a year proving otherwise, assume a child.
    if name and _key(name) in _CHILD_STARS and not (year and year >= STAR_INFO[_key(name)][1] + 16):
        return True
    if name and year:
        info = STAR_INFO.get(_key(name))
        if info and year < info[1] + 16:
            return True
    return False

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
           'shirley maclaine': 'Shirley MacLaine', 'steve mcqueen': 'Steve McQueen',
           'joel mccrea': 'Joel McCrea', "pat o'brien": "Pat O'Brien",
           'jeanette macdonald': 'Jeanette MacDonald', 'vera-ellen': 'Vera-Ellen'}
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


def identify_all(*texts) -> List[str]:
    """Every known star a text names (same matching rules as identify)."""
    import re
    blob = re.sub(r'[_\-,./()]', ' ', ' '.join(t or '' for t in texts).lower())
    words = set(blob.split())
    found = []
    for k in STAR_INFO:
        parts = k.replace('-', ' ').split()
        if k in blob or (len(parts) >= 2 and parts[0] in words and parts[-1] in words):
            k = _ALIASES.get(k, k)
            if k not in found:
                found.append(k)
    return [display_name(k) for k in found]


# Real-life married couples (both names known), for an honest "married in
# real life" note on a screen-couple photo. Only well-documented marriages.
REAL_COUPLES = {
    frozenset({'mary pickford', 'douglas fairbanks'}): 'married in 1920',
    frozenset({'clark gable', 'carole lombard'}): 'married in 1939',
    frozenset({'humphrey bogart', 'lauren bacall'}): 'married in 1945',
    frozenset({'elizabeth taylor', 'richard burton'}): 'married in 1964',
    frozenset({'william powell', 'carole lombard'}): 'married in 1931',
    frozenset({'robert taylor', 'barbara stanwyck'}): 'married in 1939',
    frozenset({'douglas fairbanks', 'joan crawford'}): '',
}


def screen_couple(*texts) -> Optional[tuple]:
    """(actress, actor) when a photo names exactly one known woman and one
    known man -- a screen (or real-life) couple."""
    names = identify_all(*texts)
    f = [n for n in names if star_gender(n) == 'f']
    m = [n for n in names if star_gender(n) == 'm']
    return (f[0], m[0]) if len(f) == 1 and len(m) == 1 and len(names) == 2 else None


# --- story captions (2026-10, after the Golden Frame Hollywood study) ---------
# Their captions narrate the MOMENT ("Lee Remick on the beach in 1958.
# Lovely!!"). Ours come from the photo's own archive description -- never
# invented -- cleaned of catalogue noise, kept to one readable sentence.
_STORY_NOISE = [
    r'(?i)\babstract/medium:.*$', r'(?i)\bnote:.*$', r'(?i)\bsubjects?:.*$',
    r'(?i)\b(library of congress|national photo company collection|bain news service)\b.*$',
    r'(?i)\b1 (negative|photographic print|photo).*$', r'(?i)^(english|description|title)\s*:\s*',
    r'(?i)\bphotograph shows\s*', r'\(SAYRE \d+\)', r'\bLCCN\w+',
]
_ABBREV = re.compile(r'(?:\b(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|Co|Mt|Ft|Wash|Cal|Calif|Pa|N\.Y|D\.C|U\.S|Gen|Col|Capt|Lt|Sgt)|\b[A-Z])$')
_FOREIGN_WORDS = re.compile(r'(?i)\b(der|die|das|und|het|een|van de|le|la|les|des|du|et|il|el|los|og|och|och)\b')
_ENGLISH_WORDS = re.compile(r'(?i)\b(the|a|an|at|on|in|with|and|of|for|from|during|her|his)\b')
_WARM = {'beach': ["Lovely!", "What a day.", "Pure summer.", "Those were the days."],
         'couple': ["What a pair.", "Pure Hollywood romance.", "Lovely!"],
         'any': ["Lovely!", "Those were the days."]}


def story_caption(desc: str, year: Optional[int] = None, warm: str = '', seed: int = 0) -> str:
    """One factual sentence describing the moment, from the archive text, or
    '' when the text isn't a clean English description."""
    t = ' '.join((desc or '').split())
    for rx in _STORY_NOISE:
        t = re.sub(rx, '', t).strip()
    # first sentence (abbreviations like "D.C." or "Mrs." don't end one)
    out, i = t, 0
    for m in re.finditer(r'\.\s+(?=[A-Z])', t):
        if not _ABBREV.search(t[:m.start()]):
            out = t[:m.start()]
            break
    t = out.strip().rstrip(';:,')
    if t.endswith('.') and not re.search(r'\b[A-Z]\.[A-Z]\.$', t):
        t = t[:-1]
    if not t or '[' in t or '?' in t or len(t) > 115:
        return ''
    words = t.split()
    if len(words) < 4 or not t[0].isupper() or not _ENGLISH_WORDS.search(t) or _FOREIGN_WORDS.search(t):
        return ''
    if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', t):
        return ''
    if year and not re.search(r'\b(18|19)\d\d\b', t):
        t = f"{t}, {year}"
    t += '.'
    pool = _WARM.get(warm) if warm else None
    if pool and seed % 3 == 0:
        t += ' ' + pool[seed % len(pool)]
    return t


def couple_caption(actress: str, actor: str, raw: str = '', category: str = '',
                   year: Optional[int] = None) -> str:
    """"Lauren Bacall and Humphrey Bogart in The Big Sleep, 1946. Married in
    real life in 1945." -- the film only when the archive names it."""
    film = re.search(r'in ["“]([^"”]{2,40})["”]', raw or '')
    film = film.group(1) if film else ''
    if not film:
        m = re.match(r'^Category:(.+?) \((?:\d{4} )?[\w ]*film\)$', category or '')
        film = m.group(1) if m else ''
    head = f"{actress} and {actor}" + (f" in {film}" if film else '') + (f", {year}." if year else '.')
    note = REAL_COUPLES.get(frozenset({_key(actress), _key(actor)}))
    return head + (f" Married in real life in {note[len('married in '):]}." if note else '')


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
    if not looks_like_person(' '.join(words)):
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
