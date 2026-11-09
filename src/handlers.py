"""Deterministic UI handlers for base-app tasks: no LLM, fixed selectors, verified results.
Each returns an outcome string and takes dry_run (stop before the final commit tap)."""
import subprocess
import time
from .safety import COMMIT_TAPS

CLOCK = "com.oneplus.deskclock"
# ponytail: picker ranges by position, OEM-specific to OnePlus Clock. None = does not wrap (AM/PM).
# Upgrade path: read min/max from the node, or a per-device handler table.
ALARM_RANGES = (12, 60, None)
TIMER_RANGES = (24, 60, 60)  # hours range not measured; only matters for wrap, and _set_all re-reads + corrects
SWIPE_PX = 250


def _pickers(d):
    from .phone import snapshot
    els, _, _ = snapshot(d)
    ps = sorted((e for e in els if "NumberPicker" in e["cls"]), key=lambda e: e["cx"])
    return ps if len(ps) == 3 else []


def _vals(ps):
    return [int(float(p["text"])) for p in ps]


def _wait(cond, timeout=6):
    t = time.time()
    while time.time() - t < timeout:
        r = cond()
        if r:
            return r
        time.sleep(0.2)
    return None


def _click(sel, tries=3):
    """Click, retrying when the node went stale between exists and click (app home still re-rendering)."""
    from uiautomator2.exceptions import RPCUnknownError
    for i in range(tries):
        try:
            return sel.click()
        except RPCUnknownError as e:
            if "StaleObject" not in str(e) or i == tries - 1:
                raise
            time.sleep(0.5)


def _steps(cur, target, n):
    """-> signed notch count (+ = swipe up). Wraps the shortest way round a picker of n values; n=None: no wrap."""
    if n is None:
        return target - cur
    diff = (target - cur) % n
    return diff if diff <= n - diff else diff - n


def _move(d, e, k, per_adb=2):
    """Move picker e by k notches (+ = swipe up). Measured on the Nord 3: an adb swipe of 250px at 300 ms+ is
    exactly 2 notches on the alarm pickers (4/4 runs; 250 ms was off by one) but 1 on the timer pickers (5/5, Nov 6);
    a u2 swipe is exactly 1 on both. So k//per_adb adb swipes + 1 u2 swipe for the remainder."""
    sign = -1 if k > 0 else 1
    pairs, odd = divmod(abs(k), per_adb)
    if pairs:
        one = f"input swipe {e['cx']} {e['cy']} {e['cx']} {e['cy'] + sign * SWIPE_PX} 300; sleep 0.1"
        subprocess.run(["adb", "-s", d.serial, "shell", "; ".join([one] * pairs)], check=True)
    if odd:
        d.swipe(e["cx"], e["cy"], e["cx"], e["cy"] + sign * SWIPE_PX, duration=0.25)
    return bool(pairs)


def _set_all(d, targets, ranges, per_adb=2):
    """Read pickers, move each by its exact notch count, re-read to verify, correct (max 3 passes)."""
    for _ in range(3):
        ps = _pickers(d)
        if not ps:
            return None
        cur = _vals(ps)
        if cur == list(targets):
            return cur
        fast = [_move(d, e, _steps(cur[i], targets[i], ranges[i]), per_adb) for i, e in enumerate(ps)]
        time.sleep(1.0 if any(fast) else 0.5)  # let the picker settle before reading
    ps = _pickers(d)
    return _vals(ps) if ps else None


def alarm(d, hour, minute=0, dry_run=False, **_):
    """Set a one-time alarm. hour is 0-23. Returns 'done', 'dry_run_ok' or 'failed: <why>'."""
    h12, ampm = (hour % 12) or 12, int(hour >= 12)
    d.app_start(CLOCK, stop=True)  # clean start: a leftover New-alarm screen would break the flow
    if not _wait(lambda: d(description="Add Alarm").exists):
        return "failed: clock alarm list not shown"
    d(description="Add Alarm").click()
    if not _wait(lambda: _pickers(d)):
        return "failed: new-alarm pickers not shown"
    got = _set_all(d, (h12, minute, ampm), ALARM_RANGES)
    if got != [h12, minute, ampm]:
        return f"failed: pickers read {got}, wanted {[h12, minute, ampm]}"
    if dry_run:
        return "dry_run_ok"
    d(text="Done").click()
    return "done" if _wait(lambda: d(description="Add Alarm").exists) else "failed: did not return to alarm list"



YT, MAPS = "com.google.android.youtube", "com.google.android.apps.maps"


def youtube_search(d, query, play=False, **_):
    """Search YouTube; play=True also taps the first video result (rows with a duration in their description, so
    mixes/playlists/ads are skipped). Verified: search_query text equals the query; player = watch_player node."""
    d.app_start(YT, stop=True)
    if not _wait(lambda: d(description="Search").exists, 10):
        return "failed: youtube home not shown"
    _click(d(description="Search"))
    box = d(resourceId=YT + ":id/search_edit_text")
    if not _wait(lambda: box.exists):
        return "failed: youtube search box not shown"
    box.set_text(query)
    d.press("enter")
    q = d(resourceId=YT + ":id/search_query")
    if not _wait(lambda: q.exists and q.get_text() == query, 8):
        return "failed: results not shown for query"
    if not play:
        return "done"
    return _play_first_video(d)


def _first_video(d):
    """-> (x, y) to tap for the first non-sponsored video row that is mostly on screen, else None.
    Rows have a duration + 'Go to channel' in their description; sponsored ones say 'Sponsored'; a row cut off by the
    screen edge (< 600 px visible) is skipped until a scroll brings it fully in. Tap lands on the thumbnail."""
    rows = d(descriptionMatches=r".*\d+ (second|minute|hour)s?.*Go to channel.*")
    for i in range(rows.count):
        try:
            info = rows[i].info
        except Exception:  # stale: the list moved while reading, next pass retries
            continue
        b = info["bounds"]
        if "ponsor" in info["contentDescription"] or b["bottom"] - b["top"] < 600:
            continue
        return (b["left"] + b["right"]) // 2, b["top"] + 250
    return None


def _skip_preroll(d, timeout=15):
    """Pre-roll ad in the player: wait for a Skip button and tap it. ponytail: Skip selector (text/desc starts with
    'Skip') NOT yet seen live (ads are intermittent); unskippable ads just run out after `timeout`, still reports done."""
    if not d(resourceId=YT + ":id/ad_progress_text").exists:
        return
    skips = (d(textMatches=r"(?i)skip.*"), d(descriptionMatches=r"(?i)skip.*"))
    t = time.time()
    while time.time() - t < timeout and d(resourceId=YT + ":id/ad_progress_text").exists:
        for skip in skips:
            if skip.exists:
                skip.click()
                return
        time.sleep(0.5)


def _play_first_video(d, scrolls=5):
    for _ in range(scrolls + 1):
        if xy := _first_video(d):
            d.click(*xy)
            if not _wait(lambda: d(resourceId=YT + ":id/watch_player").exists, 8):
                return "failed: player not shown"
            _skip_preroll(d)
            return "done"
        d.swipe_ext("up", scale=0.6)
        time.sleep(1.2)
    return "failed: no non-sponsored video found"


def maps_search(d, query, **_):
    """Search Google Maps. Verified: after Enter the results screen's search box holds the query."""
    d.app_start(MAPS, stop=True)
    if not _wait(lambda: d(description="Search here").exists, 12):
        return "failed: maps home not shown"
    _click(d(description="Search here"))
    box = d(resourceId=MAPS + ":id/search_omnibox_edit_text")  # not focused=True: two EditTexts, wrong one gets "g"
    if not _wait(lambda: box.exists):
        return "failed: maps search box not shown"
    box.set_text(query)
    time.sleep(0.8)
    d.press("enter")
    res = d(resourceId=MAPS + ":id/search_omnibox_text_box")  # results screen shows the query in content-desc, not text

    def shown():
        if not res.exists:
            return False
        i = res.info
        return query in (i.get("text"), i.get("contentDescription"))
    return "done" if _wait(shown, 8) else "failed: results not shown for query"


def timer(d, minutes, seconds=0, dry_run=False, confirm=None, **_):
    """Start a countdown timer. dry_run stops before Start. Verified: pickers read the target; live: Pause shows."""
    h, m = divmod(minutes, 60)
    d.app_start(CLOCK, stop=True)
    tab = d(resourceId=CLOCK + ":id/timer")
    if not _wait(lambda: tab.exists):
        return "failed: clock timer tab not shown"
    tab.click()
    if not _wait(lambda: _pickers(d)):
        return "failed: timer pickers not shown (a timer may already be running)"
    got = _set_all(d, (h, m, seconds), TIMER_RANGES, per_adb=1)
    if got != [h, m, seconds]:
        return f"failed: pickers read {got}, wanted {[h, m, seconds]}"
    if dry_run:
        return "dry_run_ok"
    d(description="Start").click()
    return "done" if _wait(lambda: d(description="Pause").exists) else "failed: timer did not start"


# Call / message: deterministic on purpose. Contacts, dialer and messages screens show the user's REAL contacts, so
# no LLM ever sees them, nothing is dumped or screenshotted, and only fixed test contacts can be targeted.
CONTACTS = "com.google.android.contacts"


def _open_contact(d, name):
    """Contacts -> search -> tap the exact-name result -> contact card. -> None or 'failed: ...'."""
    d.app_start(CONTACTS, stop=True)
    bar = d(resourceId=CONTACTS + ":id/open_search_bar")
    if not _wait(lambda: bar.exists, 8):
        return "failed: contacts search bar not shown"
    bar.click()
    box = d(resourceId=CONTACTS + ":id/open_search_view_edit_text")
    if not _wait(lambda: box.exists):
        return "failed: contacts search box not shown"
    box.set_text(name)
    hit = d(className="android.widget.TextView", text=name)  # TextView: the EditText also holds the name
    if not _wait(lambda: hit.exists, 5):
        return f"failed: contact {name!r} not found"
    hit.click()
    if not _wait(lambda: d(className="android.widget.TextView", text=name).exists
                 and d(className="android.widget.Button", description="Call").exists, 6):
        return "failed: contact card not shown"
    return None


def call(d, contact, dry_run=False, confirm=None, **_):
    """Stops at the Call button: dry_run -> dry_run_ok; live -> spoken yes/no gate, anything but yes cancels."""
    err = _open_contact(d, contact)
    if err:
        return err
    if dry_run:
        return "dry_run_ok"
    if not (confirm and confirm(f"Call {contact}")):
        return "cancelled_by_user"
    if not COMMIT_TAPS:
        return "confirmed_not_committed"  # user rule: never place a call
    d(className="android.widget.Button", description="Call").click()
    from .phone import snapshot  # not d.app_current(): it returns a stale package on this phone (Nov 6)
    return "done" if _wait(lambda: snapshot(d)[2] != CONTACTS, 6) else "failed: call screen not shown"


MSGS = "com.google.android.apps.messaging"


def message(d, contact, text, dry_run=False, confirm=None, **_):
    """Contact card -> Message -> type the draft -> stop at Send SMS (dry_run, or the yes/no gate)."""
    d.app_stop(MSGS)  # a running Messages resumes its conversation list (real threads) instead of the compose screen
    err = _open_contact(d, contact)
    if err:
        return err
    d(className="android.widget.Button", description="Message").click()
    box = d(resourceId=MSGS + ":id/compose_message_text")
    if not _wait(lambda: box.exists and d(text=contact).exists, 8):  # header name; the 'Texting with' banner hides once a draft exists
        d.press("home")  # never leave a private screen up
        return f"failed: compose screen for the contact not shown (box={box.exists}, name={d(text=contact).exists})"
    box.set_text(text)
    send = d(description="Send SMS")
    if not _wait(lambda: box.get_text() == text and send.exists, 4):
        return "failed: draft not typed"
    if dry_run:
        return "dry_run_ok"
    if not (confirm and confirm(f"Send message to {contact}")):
        box.clear_text()
        return "cancelled_by_user"
    if not COMMIT_TAPS:
        return "confirmed_not_committed"  # user rule: never send; the draft stays for the user to see
    send.click()
    return "done" if _wait(lambda: box.get_text() != text, 6) else "failed: message not sent"


SETTINGS, CHROME, WIRELESS = "com.android.settings", "com.android.chrome", "com.oplus.wirelesssettings"


def wifi_settings(d, **_):
    """Settings -> Wi-Fi row -> Wi-Fi page. Handler, not agent: these screens show saved network names (private).
    The Wi-Fi page is a separate package (com.oplus.wirelesssettings) that survives stopping Settings, and its toggle row
    is also labelled 'Wi-Fi': on Nov 6 a run that skipped the home-page check tapped it and turned Wi-Fi OFF. So: stop
    both packages, require the Settings home search box before the one tap, never tap anything on the Wi-Fi page."""
    d.app_stop(WIRELESS)
    d.app_start(SETTINGS, stop=True)
    row = d(className="android.widget.TextView", text="Wi-Fi")
    if not _wait(lambda: d(description="Search box").exists and row.exists and not d(text="Wi\u2011Fi").exists, 8):
        return "failed: settings home not shown"
    row.click()
    # the page title uses U+2011 (non-breaking hyphen), the settings row a plain '-'; Scan only exists while Wi-Fi is on
    return "done" if _wait(lambda: d(text="Wi\u2011Fi").exists and d(className="android.widget.Switch").exists, 6) \
        else "failed: Wi-Fi page not shown"


def chrome_search(d, query, **_):
    """Chrome url bar -> query -> Enter. Handler, not agent: Chrome reopens the user's last tab (browsing history).
    Verified: the url bar's Google search URL decodes to contain the query."""
    from urllib.parse import unquote_plus
    d.app_start(CHROME, stop=True)
    bar = d(resourceId=CHROME + ":id/url_bar")  # Chrome reopens the last tab...
    ntp = d(resourceId=CHROME + ":id/search_box_text")  # ...or its New Tab page, which has no url bar until tapped
    if not _wait(lambda: bar.exists or ntp.exists, 10):
        return "failed: chrome url bar not shown"
    (bar if bar.exists else ntp).click()
    box = d(resourceId=CHROME + ":id/url_bar", focused=True)
    if not _wait(lambda: box.exists):
        return "failed: url bar not focused"
    box.set_text(query)
    time.sleep(0.8)
    d.press("enter")
    return "done" if _wait(lambda: bar.exists and query in unquote_plus(bar.get_text() or ""), 10) \
        else "failed: search results not shown for query"


def open_app(d, pkg, **_):
    """Just open an allowlisted app. Verified: the hierarchy's package is the app (not d.app_current(), stale here)."""
    from .phone import snapshot
    d.app_start(pkg, stop=True)
    return "done" if _wait(lambda: snapshot(d)[2] == pkg, 8) else "failed: app not in foreground"



# Spotify: private app (Home/Library = the user's listening history). Handler only, no LLM, no screenshots; the only
# text read is search-result titles, and the only text spoken is one result title + artist (public catalog data).
SPOTIFY = "com.spotify.music"
_SP_PROMPT = {
    "en": "I couldn't find that exactly. Did you mean {t} by {a}? Say yes, or tell me another song.",
    "hi": "ठीक यही नहीं मिला। क्या आपका मतलब {a} का {t} है? हाँ बोलिए, या कोई और गाना बताइए।",
    "te": "సరిగ్గా అదే దొరకలేదు. మీరు {a} పాడిన {t} అనా? అవును అనండి, లేదా వేరే పాట చెప్పండి.",
    "hinglish": "Bilkul wahi nahi mila. Kya aapka matlab {a} ka {t} hai? Haan boliye, ya koi aur gaana batao."}
_SP_NONE = {
    "en": "I couldn't find any song. Which song should I search for?",
    "hi": "कोई गाना नहीं मिला। कौन सा गाना खोजूँ?",
    "te": "ఏ పాటా దొరకలేదు. ఏ పాట వెతకాలి?",
    "hinglish": "Koi gaana nahi mila. Kaun sa gaana dhoondhu?"}


def _sp_songs(d, want=None, scrolls=3):
    """Search results screen -> [(title, artist, cx, cy)] of 'Song • artist' rows, top first. Stops early when want(title, artist)."""
    import xml.etree.ElementTree as ET
    import re
    found = []
    for i in range(scrolls + 1):
        ns = [n for n in ET.fromstring(d.dump_hierarchy()).iter("node") if n.get("package") == SPOTIFY and n.get("text")]
        rid = lambda n: n.get("resource-id", "").rsplit("/", 1)[-1]
        box = lambda n: [int(v) for v in re.findall(r"\d+", n.get("bounds"))]
        subs = [n for n in ns if rid(n) == "subtitle" and n.get("text").lower().startswith("song")]
        for t in (n for n in ns if rid(n) == "title"):
            bt = box(t)
            s = next((s for s in subs if 0 <= box(s)[1] - bt[1] < 120), None)
            if s is None:
                continue
            row = (t.get("text"), s.get("text").split("•", 1)[-1].strip(), (bt[0] + bt[2]) // 2, (bt[1] + bt[3]) // 2)
            if row[:2] not in [f[:2] for f in found]:
                found.append(row)
                if want and want(*row[:2]):
                    return found
        if i < scrolls:
            d.swipe(600, 2000, 600, 900, 0.3)
            time.sleep(1)
    return found


def _sp_search(d, q, first=False):
    from urllib.parse import quote
    if first:
        d.app_stop(SPOTIFY)  # a running Spotify may be on a private screen; the deep link replaces it with search
    subprocess.run(["adb", "-s", d.serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d",
                    f"spotify:search:{quote(q)}", SPOTIFY], capture_output=True, stdin=subprocess.DEVNULL)
    return _wait(lambda: d(resourceId=SPOTIFY + ":id/search_content_recyclerview").exists, 12)


def _sp_play(d, row, refind=False):
    if refind:  # candidates were collected while scrolling: saved coordinates are stale, scroll back and re-locate
        for _ in range(4):
            d.swipe(600, 900, 600, 2000, 0.2)
        row = (_sp_songs(d, lambda t, a: (t, a) == row[:2]) or [row])[-1]
    d.click(row[2], row[3])
    def playing():  # row titles can carry a suffix the player drops ("X - Medley" vs "X"): prefix match either way
        t = d(resourceId=SPOTIFY + ":id/track_info_view_title")
        if not t.exists:
            return False
        a, b = (t.get_text() or "").lower(), row[0].lower()
        if not (a and (a.startswith(b) or b.startswith(a))):
            return False
        if d(resourceId=SPOTIFY + ":id/play_pause_button", description="Play").exists:  # Spotify restores the last track paused
            d(resourceId=SPOTIFY + ":id/play_pause_button", description="Play").click()
            time.sleep(1)
        return d(resourceId=SPOTIFY + ":id/play_pause_button", description="Pause").exists
    ok = _wait(playing, 10)
    return "done" if ok else "failed: player did not show the song playing"


def spotify_play(d, title, artist="", lang="en", confirm=None, dry_run=False, **_):
    """Deterministic search + exact title/artist match -> tap -> player verifies. No exact match: offer the top song
    (yes plays it), or take a new song by voice; a reply is never auto-played, always offered first. Max 3 rounds.
    dry_run stops before the row tap."""
    from .safety import NO, STOP, is_yes, words
    reply = getattr(confirm, "reply", None)
    norm = lambda s: s.lower().strip()
    is_hit = lambda t, a: norm(t) == norm(title) and (not artist or norm(artist) in norm(a))
    q, exact = f"{title} {artist}".strip(), True
    for i in range(3):
        if not _sp_search(d, q, first=(i == 0)):
            d.press("home")
            return "failed: spotify search not shown"
        songs = _sp_songs(d, is_hit if exact else None)
        hit = next((r for r in songs if is_hit(*r[:2])), None) if exact else None
        if hit:
            return "dry_run_ok" if dry_run else _sp_play(d, hit)
        if not reply:
            return "failed: no exact match"
        ans = reply((_SP_PROMPT.get(lang, _SP_PROMPT["en"]).format(t=songs[0][0], a=songs[0][1]) if songs
                     else _SP_NONE.get(lang, _SP_NONE["en"])))
        if songs and is_yes(ans):
            return "dry_run_ok" if dry_run else _sp_play(d, songs[0], refind=True)
        if not words(ans) or set(words(ans)) <= (NO | STOP):
            return "cancelled_by_user"
        q, exact = ans.strip(), False
    return "failed: no match after 3 tries"


# Only tasks with a verified handler are listed; the router may name others, they fall back to the agent loop.
HANDLERS = {
    "alarm": lambda d, r, dry_run, confirm: alarm(d, r["hour"], r.get("minute", 0), dry_run=dry_run),
    "timer": lambda d, r, dry_run, confirm: timer(d, r["minutes"], r.get("seconds", 0), dry_run=dry_run),
    "youtube_search": lambda d, r, dry_run, confirm: youtube_search(d, r["query"], play=r.get("play", False)),
    "maps_search": lambda d, r, dry_run, confirm: maps_search(d, r["query"]),
    "wifi_settings": lambda d, r, dry_run, confirm: wifi_settings(d),
    "open_app": lambda d, r, dry_run, confirm: open_app(d, r["pkg"]),
    "chrome_search": lambda d, r, dry_run, confirm: chrome_search(d, r["query"]),
    "call": lambda d, r, dry_run, confirm: call(d, r["contact"], dry_run, confirm),
    "message": lambda d, r, dry_run, confirm: message(d, r["contact"], r["text"], dry_run, confirm),
    "spotify_play": lambda d, r, dry_run, confirm: spotify_play(d, r["query"], r.get("artist", ""), r["lang"], confirm, dry_run),
}
