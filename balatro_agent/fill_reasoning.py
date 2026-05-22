"""
Fill in reasoning for all 176 entries in manual_run_01.jsonl
"""
import json

REASONING = {
    # ── Ante 1 ──────────────────────────────────────────────────────────────
    0: "Starting the run; no reason to skip the Small Blind — taking every blind early builds money and keeps runs alive.",

    # A1R1 hand play
    1: "Hand has only a Pair of 7s; discarded the disconnected K, J, and 7D to chase a straight with the 8-7-6-5 run already in hand.",
    2: "Drew a 4D completing an 8-7-6-5-4 straight; played it for the highest scoring hand available.",
    3: "Played a Flush last hand; now have KD,QD from draw — discarding AC,9C,5H,2H to keep four diamonds and chase another flush.",
    4: "Five diamonds landed (KD,QD,JD,9D,6D) — played the Flush, strongest hand available by a wide margin.",

    # A1R1 shop
    5:  "Fortune Teller and The Magician don't fit the current build; rerolled hoping for a better joker or planetary upgrade.",
    6:  "Chose Square Joker over Photograph — Square Joker gains +4 chips every time a 4-card hand is played, and Two Pair (which often uses exactly 4 or 5 cards) is a common pattern I plan to exploit to stack chip bonuses.",
    7:  "Fortune Teller is still weak for this build; rerolled again to look for a better card option.",
    8:  "Pluto upgrades Straight level and Mercury upgrades Pair level — neither is the primary hand I'm building around, so skipped the Celestial Pack.",
    9:  "Only $1 left; Fortune Teller ($6) and The Magician ($3) are both out of budget. Left shop empty-handed.",

    10: "Moved on to Round 2; the Small Blind is beatable with the current joker lineup.",

    # A1R2 hand play
    11: "Best hand is Two Pair but only draws high cards; discarded 9H and 8D (off-suit junk) hoping to improve club count for a flush.",
    12: "Drew 3C giving AC-9C-4C-3C-2C — played the Club Flush, best hand available.",
    13: "Three Queens in hand; discarded low junk (7H, 5C) to keep AH,KD,QH,QC,QD,JD and draw for a Full House or Four of a Kind.",
    14: "Still three Queens; last discard — removed AH,6S,4D to keep the KD,QH,QC,QD,JD core and draw for a paired King to make Full House.",
    15: "Drew KC giving KC-KD-QH-QC-QD; played the Full House (two Kings, three Queens) — highest scoring hand possible.",

    16: "Greedy Joker ($5) and Wily Joker ($4) don't synergize with the flush/straight build; saved the $7 for next ante.",
    17: "Ante 1 Boss Blind — with joker support the chip target should be reachable.",

    # A1R3 hand play
    18: "A-K-J core is good for a broadway straight; discarded the second Jack (JD) plus all junk (9C,7H,3C,2S) to keep AD,KH,JS and draw 5 fresh cards hoping to land Q and T for an A-K-Q-J-T straight.",
    19: "Drew Q and T giving A-K-Q-J-T broadway straight; played it immediately for maximum chips.",

    # ── Ante 2 ──────────────────────────────────────────────────────────────
    20: "Shop has Mystic Summit and Drunkard — neither is ideal. Rerolled ($5) to find better jokers or a useful Arcana pack.",
    21: "Pack offered Strength and The Moon; took Strength to upgrade low-rank cards and close gaps in flush or straight draws.",
    22: "Remaining shop items aren't useful; rerolled again to find another Arcana pack worth opening.",
    23: "Accidentally skipped The Hermit — did not mean to pass on the money-doubling tarot. Misclick.",
    24: "Mystic Summit (+15 Mult when 0 discards remain) is strong for end-of-round cleanup; bought it to power up the final hand each round.",
    25: "Mystic Summit locked in, shop is thin. Left with $11 — saving money for the next ante's shop.",

    26: "Ante 2 Small Blind — straightforward, moved in.",

    # A2R4 hand play
    27: "Pair of Jacks is the best hand but junk in slots 5-7; discarded 7C,6H,4D to draw for a straight or pair improvement.",
    28: "Drew Two Pair (JS-JH, 9H-9D) — played it as the best scoring hand with Pairs of Jacks and 9s.",
    29: "Pair of Queens is fine but off-suit junk at the bottom; discarded 5S,3D,2C to draw for a better hand.",
    30: "Drew Two Pair (QS-QD, 4H-4C) but still have 2S; discarded 2S as the final discard to redraw for a kicker improvement.",
    31: "Discards exhausted; Two Pair (QQ,44) is the best available — played it.",

    32: "Popcorn gives +5 Chips per hand played but degrades; bought it while cheap since current hands per ante are manageable.",
    33: "The Tribe ($8) is too expensive for the chip return; rerolled to look for a Standard Pack with enhanced playing cards.",
    34: "Celestial Pack had Mars, Mercury, Saturn, Pluto — none align with the primary scoring hands this run, skipped.",
    35: "Shop cleared — nothing left worth buying at this budget.",

    36: "Ante 2 Boss Blind — jokers are accumulating nicely, moved in.",

    # A2R5 hand play
    37: "A-K-Q-J core is great for a broadway straight; discarded 9S,9C,3H,2H junk to draw a T or suited cards.",
    38: "Drew T giving A-K-Q-J-T broadway Straight; played it immediately.",

    39: "Business Card and Vampire don't fit the build; rerolled to look for a better joker or a Spectral pack.",
    40: "Jumbo Spectral pack had Wraith — chose it as a high-roll for a rare joker worth the $0 money reset. Generated The Trio (+3 Mult per Three of a Kind played), which stacks nicely with face-card heavy hands.",
    41: "Joker slots are full with strong synergies; left the shop with The Trio locked in.",

    42: "Ante 2 Big Blind (boss) — strong joker lineup, went in.",

    # A2R6 hand play (actually A2R6 transitions to A3)
    43: "Drew a perfect A-K-Q-J-T broadway Straight on the opening hand; played it straight away for big chips.",

    # ── Ante 3 ──────────────────────────────────────────────────────────────
    44: "Only a basic Joker ($2) in shop — not worth buying. Rerolled for better options.",
    45: "Pluto and Mars are planet upgrades; Pluto boosts Straight and Mars boosts Full House. Neither is the primary hand right now — skipped.",
    46: "Shop left with only a basic Joker; not worth buying. Left to save money.",

    47: "Ante 3 Small Blind — comfortable with current build.",

    # A3R7 hand play
    48: "Spotted a Q-J-T-9-8 Straight in hand (indices 0,1,2,4,5); played it immediately for strong chips.",

    49: "Swashbuckler adds +Mult equal to all jokers' sell values — with 5 jokers currently selling for ~$13 total, that's +13 Mult for $6. Great value; sold Superposition to free a joker slot.",
    50: "Shop is empty of useful cards after buying Swashbuckler; rerolled to find a Celestial pack.",
    51: "Celestial pack had Neptune (Flush) and Jupiter (Full House) — Flush level upgrade is relevant but low priority right now; skipped.",
    52: "Nothing useful remaining in shop; left to conserve funds.",

    53: "Ante 3 Boss Blind — jokers are strong, went in.",

    # A3R8 hand play
    54: "J-T-8-7 form a 4-card straight draw (need 9 for J-T-9-8-7); discarded the duplicate 7H and junk (4C,3S,2D), deliberately breaking the 7s pair, to keep the straight-draw core and redraw for a completing 9.",
    55: "Drew a Q-J-T-9-8 Straight (indices 0,1,3,4,6); played it immediately.",
    56: "Four clubs in hand (JC,9C,6C,5C) — discarded the extra spade 5S and off-suit AH to keep the 4-club flush draw core plus TS,7S as backup, and draw 2 more cards for a completing club.",
    57: "Have JC,TS,9C,7S in hand plus 9H as duplicate — discarded 9H to draw; got 8C completing J-9-8-6-5 clubs for a flush.",
    58: "Five clubs available (JC,9C,8C,6C,5C) — played the Flush, best hand available with 0 discards left.",

    # ── Ante 4 ──────────────────────────────────────────────────────────────
    59: "The Trio (Spectral rare joker) hasn't been synergizing — Three of a Kind rarely hits. Sold it ($4) to free a slot and buy Photograph for free.",
    60: "Photograph (×2 Mult for first face card played) is excellent with straights and flushes that include J/Q/K; bought it for free and left shop.",
    61: "Celestial Pack had Earth (Two Pair) and Mars (Full House) — neither is the primary target hand; skipped.",
    62: "Nothing useful after the pack; left shop.",
    63: "Standard Pack had Glass, Base, Lucky cards — no specific rank needed right now; skipped.",
    64: "Popcorn degrades (-4 chips per hand); with several hands left it would drain significantly. Sold Popcorn ($2) to free a slot for Golden Joker.",
    65: "Golden Joker gives flat +4 chips per hand with no degradation — better long-term than Popcorn. Bought it free from shop.",

    66: "Ante 4 Small Blind — solid joker setup, went in.",

    # A4R9 hand play
    67: "Hand has only a Pair of 3s with junk; discarded KC,3H,3D to keep T,9C,7C,6H,5S — one card from a T-9-8-7-6 straight draw.",
    68: "Drew Q,J giving Q-J-T-9-8 Straight; played it immediately.",

    69: "Shop has nothing worth buying at current prices; left with $25 to save for Ante 5.",
    70: "Celestial Pack had Earth and Mercury — Two Pair and Pair upgrades aren't primary hands; skipped.",
    71: "Nothing changed; shop still empty of useful items.",
    72: "Earth and Mercury again — skipped, same reasoning.",
    73: "Wily Joker gives +40 chips when a played hand contains a Jack — strong chip bonus for the Straight and Flush builds that regularly include Jacks.",
    74: "Shop has Raised Fist and The Chariot tarot; neither is high priority. Left with $10 banked.",

    75: "Ante 4 Boss Blind — with the joker suite it's manageable.",

    # A4R10 hand play
    76: "Two Lucky 9s make Two Pair (9-9, 3-3) attractive — Lucky cards can proc extra chips/gold. Played Two Pair [2,3,4,5,6].",
    77: "Big money from last blind; A-K-K hand with junk — discarded JD,TS,5D to draw for a third King or flush setup.",
    78: "Still two Kings; discarded JC,2S to keep AH,KS,KH,TH,4H — four hearts in hand, chasing a heart flush.",
    79: "Drew 6H giving AH-KH-TH-6H-4H — five hearts! Played the Heart Flush.",
    80: "Two Pair (KK,66) is the best available; played it for solid chips.",

    81: "Ancient Joker is available for free — it gives +50 Mult per Flush played, which is game-changing for this flush-heavy build. Sold Golden Joker ($3) to free a slot and bought Ancient Joker.",
    82: "Ancient Joker acquired; nothing else needed. Left shop.",
    83: "Standard Pack had only basic and Glass cards — no specific rank needed; skipped.",
    84: "Seltzer (adds Wild cards to played hands) helps guarantee flush completions by acting as wild suit — bought it to supplement the flush strategy.",
    85: "Shop has 8 Ball and Flower Pot — expensive jokers that don't synergize; left shop with $43 banked.",

    86: "Ante 4 Boss Blind — Ancient Joker + flush build makes this very achievable.",

    # A4R11 hand play
    87: "Two Pair (AA,QQ) is the best available hand; played it with the high Ace pairs for maximum chips.",
    88: "Pair of 7s (7H,7D) with Lucky 9C for chip/gold trigger — discarded the isolated KH,3D,2D to keep the pair core plus 6H and draw 3 cards hoping for a third 7, another pair for Two Pair, or more hearts toward a flush.",
    89: "Four hearts (JH,TH,7H,6H) in hand — discarded TS,9C(Lucky),7D to keep the hearts and draw for a fifth heart.",
    90: "Drew 4H giving JH-TH-7H-6H-4H — Heart Flush! With Ancient Joker that's +50 Mult. Played it.",

    # ── Ante 5 ──────────────────────────────────────────────────────────────
    91: "The Magician tarot for $3 enhances 2 random cards to Lucky (bonus chips/gold on trigger) — cheap way to add value to the deck.",
    92: "Ice Cream joker adds +4 Chips each time a hand is played — good passive chip stacking with no downside.",
    93: "The Lovers tarot enhances a random card in hand to Wild — Wild cards help complete flushes; bought it for $3.",
    94: "Shop is out of useful items; left with consumables and $41 saved.",

    95: "Ante 5 Small Blind — strong build, went in.",

    # A5R12 hand play
    96: "Best hand is only a Pair of 6s with junk; discarded QC,3S,2C to draw for a better hand or flush setup.",
    97: "Drew Two Pair (JH-JD, 9H-9D); played Two Pair [1,2,3,4,6] for solid chips.",
    98: "Two Glass Queens and a pair of Jacks — played 4-card Two Pair [0,1,2,3] (QS, QS-Glass, JH, JC) to feed Square Joker's chip counter; the Glass Queen multiplies scoring on this hand.",

    99: "The Wheel of Fortune tarot ($3) has a chance to add a foil/holo/polychrome edition to a random joker — cheap investment for a potential big upgrade.",
    100: "The Duo joker ($8) gives +2 Mult each time a Pair or higher is played — constant Mult bonus for this Pairs/Flush heavy build.",
    101: "Shop is empty of cards; rerolled to find jokers or a pack worth buying.",
    102: "Jumbo Arcana Pack opened — selected index 0 for the best available tarot enhancement.",
    103: "After the pack, shop is empty; rerolled again.",
    104: "Nothing left worth buying; left shop with $34.",

    105: "Ante 5 Small Blind — solid setup, went in.",

    # A5R13 hand play
    106: "Hand has only a Pair of 8s with junk; discarded 6D,4S,2C to keep J(Lucky),9H(Wild),8H,8C and draw for a Three of a Kind or flush.",
    107: "Drew 9C(Lucky) and 8S completing 8S-8H-8C Three of a Kind with 9H-9C pair — Full House! Played Full House [2,3,4,5,6] for maximum scoring.",
    108: "After that strong hand, new draw shows only KS-QS-QD pair; discarded 8D,5D,4C to draw for a paired King or better.",
    109: "Drew Two Pair (QQ, TT) — played it as the best available hand.",

    110: "The Sun tarot ($3) — upgrades the level of a specific hand (likely Full House to capitalize on the strong last hand); cheap buy.",
    111: "Death tarot ($3) — copies a left-neighbor card onto a right-neighbor card, useful for getting more Lucky/Wild/Glass copies; bought it.",
    112: "Shop empty after buying two tarots; rerolled to find another joker.",
    113: "Flower Pot joker ($6) gives +15 Mult when played hand contains all 4 suits — strong with flush-adjacent mixed-suit hands; bought it.",
    114: "Riff-raff creates 2 Common Jokers when selling — bought it to potentially replace weaker jokers.",
    115: "Hallucination (+1/4 chance of creating a Tarot on each hand played) is excellent — passive tarot generation for card upgrades; bought it.",
    116: "Marble Joker ($6) adds a Stone Card to the deck each ante — Stone Cards give flat chips no matter what hand is played, good for chip padding.",
    117: "Shop still has items but running low on money; left with $18 to manage.",

    118: "Ante 5 Boss Blind — large joker collection, confident going in.",

    # A5R14 hand play — only one hand then round over (made it in one hand)
    119: "Pair of Queens plus high kickers; played the Pair [0,2,3,4,5] using AC as the strong kicker.",

    # ── Ante 6 ──────────────────────────────────────────────────────────────
    120: "Lusty Joker and Walkie Talkie don't fit current build; rerolled to find something useful.",
    121: "Arcana Pack had no tarots matching current priorities; skipped.",
    122: "Still the same weak items; rerolled again looking for useful jokers.",
    123: "Celestial Pack had Neptune (Flush) and Jupiter (Full House) — Flush upgrade could help but money is tight; skipped to save funds.",
    124: "After two rerolls nothing compelling; left shop with $21.",

    125: "Ante 6 Small Blind — building momentum, went in.",

    # A6R15 hand play
    126: "Best hand is only a Pair of 8s with off-suit junk; discarded 8S,8C,6C to keep A-K-Q-J and draw for a straight.",
    127: "Drew K(Glass),K and J(Lucky) giving a Two-Pair (KK,JJ) and also a straight draw A-K-Q-J-T; played the Straight [0,2,3,4,6] for higher scoring with face cards triggering Photograph.",

    128: "Shop has The High Priestess ($3) — creates 2 Planets, useful for hand level upgrades; rerolled to find a Arcana pack first.",
    129: "Jumbo Arcana Pack opened — selected Strength tarot at index 0 to upgrade low cards and improve hand consistency.",
    130: "The High Priestess ($3) generates 2 Planet cards — cheap way to level up hands; bought it.",
    131: "Shop empty after two tarot buys; rerolled looking for a joker or pack.",
    132: "Popcorn (+4 Mult per hand, degrades) is available — even a few hands of bonus Mult is worth the $8 cost given current high chip targets.",
    133: "Joker slots full with good synergies; left shop.",

    134: "Ante 6 Boss Blind — confident with joker depth.",

    # A6R16 hand play
    135: "Pair of Kings — one is a Glass card for ×2 scoring — is a strong core; discarded 8C,7D,3S junk to keep KC,Glass-KC,QH,TD and draw 3 cards hoping to hit a second pair or trips for Full House.",
    136: "Got K(Glass), Q alongside the pair core; still have junk — discarded 7S,2S for a final draw.",
    137: "Drew QH and QC giving Two Pair (K-K, Q-Q); played Two Pair [0,1,2,3,6] with both Glass Kings for multiplied scoring.",

    # ── Ante 7 ──────────────────────────────────────────────────────────────
    138: "Shop has no cards, only Blank voucher and expensive packs; rerolled to see if better items appear.",
    139: "Celestial Pack had 4 planets (Saturn,Neptune,Jupiter,Mercury) — none are the primary hands being scored right now; skipped.",
    140: "Nothing useful after reroll; left shop.",

    141: "Ante 7 Small Blind — joker roster is strong.",

    # A7R17 hand play
    142: "Three 3s won't score enough at Ante 7's chip targets — low-rank trips fall far short of the blind. Discarded all 5 (the trips + Gold-5S + 2D) to keep just AD,KS and draw 5 fresh cards for a shot at a Full House or Straight.",

    143: "Wily Joker and Chaos the Clown don't fit; rerolled to find something better.",
    144: "Celestial Pack with Venus, Mercury, Earth — Pair and Two Pair upgrades are secondary; skipped.",
    145: "Nothing useful; left shop.",

    146: "Ante 7 Small Blind — moved in.",

    # A7R18 hand play
    147: "JH-JC-JD three Jacks plus 6S-6C pair — perfect Full House! Played it [1,2,3,4,5] for massive scoring with Photograph boosting the first Jack.",

    148: "Shop has Mars planet and Arcana Pack; rerolled looking for a joker upgrade.",
    149: "Celestial Pack: Neptune and Saturn — Flush and Straight upgrades; not primary focus right now.",
    150: "Arcana Pack — selected index 0 for the best tarot enhancement available.",
    151: "Got Mars planet consumable; nothing more to buy. Left shop.",

    152: "Ante 7 Boss Blind — took it on.",

    # A7R19 hand play
    153: "0 discards left and 4 hands remaining; played a 3-card Pair of 7s [4,5,6] to get chips flowing — 3-card hand also feeds Square Joker if conditions align.",
    154: "Pair of 9s (Wild+Lucky) with K-Q kickers; played Pair [1,2,3,4,5] using the Wild and Lucky 9s for bonus triggers.",

    # ── Ante 8 ──────────────────────────────────────────────────────────────
    155: "The Emperor tarot creates 2 Kings — great for Full House/Four of a Kind setups; bought it for $3.",
    156: "Blue Joker ($5) gives +2 Chips per card remaining in deck — with a large deck that's significant chip padding; bought it.",
    157: "Shop has remaining items but the build is solid; left with $28.",

    158: "Ante 8 Small Blind — committing with full strength.",

    # A8R20 hand play
    159: "Two Pair (QQ, 77) is best but have junk — discarded 4H,3S to draw for a King or Ace improvement.",
    160: "Drew more Qs and 9H(Wild) but no upgrade — played 4-card Two Pair [2,3,5,6] (QS-Glass, QH, 7S, 7D) to feed Square Joker with the Glass Queen multiplying scoring.",
    161: "After scoring, new draw has only Pair of 9s (Wild+Lucky) with junk; discarded 4S,2C to improve.",
    162: "Drew 4C and Steel 4D — have 9-9 pair and 4-4 pair (with Steel 4D boosting held chips); played 4-card Two Pair [3,4,5,6] (9H,9C,4C,4D-Steel) to feed Square Joker.",

    163: "The Wheel of Fortune ($3) has a chance to upgrade a joker's edition — cheap gamble for a big multiplier boost; bought it.",
    164: "The Empress tarot ($3) enhances 2 cards to add Mult effect — bought it to buff high-value cards.",
    165: "Shop empty of cards after tarots; rerolled to find one more useful item.",
    166: "The Order joker ($0) gives +3 Mult for each Straight played — adding it for free bolsters chip output on Straight hands.",
    167: "Shop has The High Priestess and Greedy Joker — High Priestess is useful but running low on money; left shop to conserve.",

    168: "Ante 8 Boss Blind — this is the final ante! Going in with everything.",

    # A8R21 hand play (final round)
    169: "Four clubs already in hand (AC,QC,9C,5C) — discarded the off-suit TS,4S,3H to keep all four clubs and draw one card for a club flush.",
    170: "Drew clubs giving AC-QC-QC-9C(Lucky)-5C — a Flush! Played Club Flush [2,3,4,5,6] for maximum scoring with Ancient Joker's +50 Mult.",
    171: "New hand has only a Pair of Queens with junk; discarded 8C,6S,5S(Gold) [4,5,6] to draw for a Full House or Three of a Kind upgrade.",
    172: "Drew QH,QD,T(Lucky),TH,TC giving Full House (QQ + TTT) — played Full House [1,2,3,4,5] with Photograph boosting the first Queen.",
    173: "Drew K-J-9-7-2 of Hearts giving a Heart Flush! Played it [0,1,2,3,6] — Ancient Joker activates for massive scoring.",
    174: "Last discard available; hand has Glass QS with junk — discarded 7D,2S [1,6] to keep Glass Q and the small pairs (5-5, 3-3) for a Two Pair play.",
    175: "Final hand with Mult Cards (5H,5D) boosting scoring — played Two Pair [2,3,4,5,6] (3C,3D,5H-Mult,5D-Mult,2C) to squeeze maximum chips from the Mult-enhanced cards.",
}

def main():
    path = "runs/manual_run_01.jsonl"
    with open(path) as f:
        entries = [json.loads(l) for l in f if l.strip()]

    print(f"Loaded {len(entries)} entries")
    missing = []

    for i, entry in enumerate(entries):
        if i in REASONING:
            entry["params"]["reasoning"] = REASONING[i]
        else:
            missing.append(i)

    if missing:
        print(f"WARNING: No reasoning for entries: {missing}")

    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    filled = sum(1 for e in entries if e["params"].get("reasoning"))
    print(f"Saved — {filled}/{len(entries)} entries now have reasoning")

if __name__ == "__main__":
    main()
