"""A shot's speaking actions, for a render part that does not say the shot's lines (shot_share.lines_here).

A shot's lines are all said in one part. Where the shot goes on in another part, its beat still read "she speaks in a soft
voice" without a <d> line to say, and H3 made up words for it (75 s ref2va project, 2026-11)."""
import re

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# A speaking action written into a shot's text: "... and speaks in a slow, gravelly voice", "@Kira answers, then turns",
# "goes on explaining". The words themselves are the shot's spoken lines (<d> ... </d>).
_SPEECH = re.compile(r"\b(?:(?:speak|talk|answer|ask|whisper|murmur|mutter|shout|yell|exclaim|explain|respond|tell)(?:s|ing)"
                     r"|says|saying|repl(?:ies|ying)|call(?:s|ing)\s+out"
                     r"|(?:goes|going|carries|carrying)\s+on\b(?!\s+(?!speaking|talking|explaining)\w+ing\b)"
                     r"|(?:keeps|keeping|continues|continuing)\s+(?:speaking|talking|explaining|to\s+(?:speak|talk|explain))"
                     r"|(?:starts|starting|begins|beginning|about)\s+to\s+(?:speak|talk|ask|answer|explain))\b",
                     re.IGNORECASE)
_NOUN_BEFORE = re.compile(r"\b(?:a|an|the|of|her|his|their|its|no)\s+$", re.IGNORECASE)   # "her whispers", "the answer"
# "a slow, gravelly voice" is one phrase: its comma and "and" do not end the clause
_VOICE_PHRASE = re.compile(r"\b(?:a|an|her|his|their|the)\s+(?:[\w'-]+(?:,\s*|\s+and\s+|\s+)){0,4}?(?:voice|tone)\b", re.IGNORECASE)
# "and" between two names or things ("@Joss and @Kira", "and the woman") joins them, it does not start a clause
_CLAUSE = re.compile(r"(,\s+|;\s+|\s+(?=(?:while|then|as|but)\s|and\s+(?!(?:a|an|the|her|his|their)\b|@)))", re.IGNORECASE)
_JOINER = re.compile(r"^(?:and\s+then|and|then)\s+", re.IGNORECASE)
_CONNECTOR = re.compile(r"^(?:and\s+then|and|then|while|as|but)\s+", re.IGNORECASE)
_LEAD_BEAT = re.compile(r"^(\d+(?:[.,]\d+)?\s*s?\s*[–-]\s*\d+(?:[.,]\d+)?\s*s(?:ec(?:onds?)?)?\s*:\s*)", re.IGNORECASE)


def _speech_at(clause):
    """Where the clause's speaking verb starts, or None."""
    return next((m.start() for m in _SPEECH.finditer(clause) if not _NOUN_BEFORE.search(clause[:m.start()])), None)


def _without_speech_sentence(sentence):
    """One sentence without its speaking clauses; "" when it was only speech."""
    stop = sentence[-1:] if sentence[-1:] in ".!?" else ""
    body = _VOICE_PHRASE.sub(lambda m: m.group(0).replace(",", "\x00").replace(" and ", "\x01"), sentence[:len(sentence) - len(stop)])
    parts = _CLAUSE.split(body)
    kept, dropped = [], None
    for n, clause in enumerate(parts[0::2]):
        sep = parts[2 * n - 1] if n else ""
        at = _speech_at(clause)
        if at is not None:
            connector = _CONNECTOR.match(clause[:at])
            connector = connector.group(0) if connector else ""
            dropped = (sep, connector, clause[len(connector):at].strip())
            continue
        if dropped:
            # whoever said the words goes on with the next step ("@Kira answers, then turns" -> "@Kira turns")
            dropped_sep, connector, subject = dropped
            if subject and _JOINER.match(clause):
                sep, clause = dropped_sep, connector + subject + " " + _JOINER.sub("", clause)
            elif not kept:
                sep, clause = "", _CONNECTOR.sub("", clause)
            dropped = None
        kept.append(sep + clause)
    text = "".join(kept).strip().replace("\x00", ",").replace("\x01", " and ")
    return text[:1].upper() + text[1:] + stop if text else ""


def without_speech(text, dialogue):
    """A shot's text without its speaking actions, for a part that does not say the shot's lines (lines_here). The beat
    still read "she speaks in a soft voice" there, with no <d> line to say, and H3 made up words for it (75 s ref2va
    project, 2026-11). The rest of each sentence stays: "@Joss pats the hull and speaks in a slow voice, while @Kira's lips
    stay closed" keeps "@Joss pats the hull, while @Kira's lips stay closed". A time beat left with nothing goes, with its
    mark. `dialogue` matches spoken lines, which are left as they are."""
    out = []
    for line in text.splitlines():
        if dialogue.match(line.strip()):
            out.append(line)
            continue
        sentences = []
        for sentence in _SENTENCE.split(line):
            mark = _LEAD_BEAT.match(sentence)
            mark = mark.group(1) if mark else ""
            rest = _without_speech_sentence(sentence[len(mark):].strip()) if sentence.strip() else ""
            if rest:
                sentences.append(mark + rest)
        out.append(" ".join(sentences))
    return "\n".join(out)


def without_lines(text, dialogue):
    """A shot's text for a part that does not say its lines: without the lines and, when it had any, without the speaking
    actions that went with them. A shot without lines keeps its text as written."""
    lines = text.splitlines()
    kept = [line for line in lines if not dialogue.match(line.strip())]
    return without_speech("\n".join(kept), dialogue) if len(kept) < len(lines) else "\n".join(kept)
