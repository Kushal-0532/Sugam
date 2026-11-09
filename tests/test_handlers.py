from src.handlers import _steps


def test_steps_wrap_and_ampm():
    # hour (12-wrap), minute (60-wrap): shortest way round; + = swipe up
    assert _steps(10, 7, 12) == -3 and _steps(12, 1, 12) == 1 and _steps(1, 12, 12) == -1
    assert _steps(59, 0, 60) == 1 and _steps(0, 59, 60) == -1 and _steps(0, 30, 60) in (30, -30)
    assert _steps(4, 5, 60) == 1 and _steps(10, 50, 60) == -20
    # am/pm (n=None) does not wrap: plain sign
    assert _steps(1, 0, None) == -1 and _steps(0, 1, None) == 1 and _steps(1, 1, None) == 0
    # timer: 15 min -> 5 min is 10 down, 0 s stays
    assert _steps(15, 5, 60) == -10 and _steps(0, 0, 60) == 0


def test_check_route_degrades_to_agent():
    from src.planner import check_route
    t = "x"
    assert check_route({"task": "alarm", "hour": 7, "minute": 30, "lang": "en", "goal": "g"}, t)["task"] == "alarm"
    assert check_route({"task": "alarm", "hour": 7, "lang": "en", "goal": "g"}, t)["task"] == "alarm"  # minute defaults 0
    for bad in ({"task": "alarm", "lang": "en"}, {"task": "alarm", "hour": 25}, {"task": "alarm", "hour": True},
                {"task": "alarm", "hour": 7, "minute": 60}, {"task": "youtube_search", "query": " "},
                {"task": "bogus"}, "notadict", None):
        assert check_route(bad, t) == {"task": "agent", "lang": "en", "goal": t}, bad


def test_check_route_bad_goal_uses_transcript():
    from src.planner import check_route
    assert check_route({"task": "agent", "lang": "en", "goal": "agent"}, "call Test Amma")["goal"] == "call Test Amma"
    assert check_route({"task": "agent", "lang": "en"}, "call Test Amma")["goal"] == "call Test Amma"
    assert check_route({"task": "agent", "lang": "en", "goal": "Call the contact Test Amma"}, "x")["goal"] == "Call the contact Test Amma"


def test_check_route_timer_and_contacts():
    from src.planner import check_route
    t = "x"
    assert check_route({"task": "timer", "minutes": 5, "lang": "hi", "goal": "set a 5 minute timer"}, t)["task"] == "timer"
    for bad in ({"task": "timer"}, {"task": "timer", "minutes": 0}, {"task": "timer", "minutes": "5"},
                {"task": "timer", "minutes": 5, "seconds": 60}):
        assert check_route(bad, t)["task"] == "agent", bad
    ok = {"task": "message", "contact": "Test Papa", "text": "मैंने खाना खा लिया", "lang": "hi", "goal": "text papa"}
    assert check_route(ok, t)["task"] == "message"
    assert check_route({"task": "call", "contact": "Test Amma", "lang": "te", "goal": "call amma"}, t)["task"] == "call"
    # privacy: unknown contact / empty body never falls back to the agent loop
    for bad in ({"task": "call", "contact": "Amma"}, {"task": "call"}, {"task": "message", "contact": "Test Papa", "text": " "},
                {"task": "message", "contact": "Test Anna", "text": "hi"}):
        assert check_route(bad, t)["task"] == "blocked_contact", bad


def test_reply_language_follows_the_script():
    from src.planner import check_route
    r = {"task": "agent", "lang": "hinglish", "goal": "text papa please"}
    assert check_route(dict(r), "Test Papa को message भेजो")["lang"] == "hi"
    assert check_route(dict(r), "Test అమ్మకి call చెయ్యి")["lang"] == "te"
    assert check_route(dict(r), "Test Papa ko message bhejo")["lang"] == "hinglish"  # Latin script: the model's call stands


def test_multi_step_requests_skip_search_handlers():
    from src.planner import beyond_search, check_route
    for t in ("open youtube, search for 8bitryan and play his latest fnaf related video",
              "open 8bitryan's channel, go to videos and scroll until a fnaf video comes up",
              "search for cats then open the first video", "cats search karke play karo",
              "YouTube पर भक्ति गाने खोजकर, फिर चलाओ"):
        assert beyond_search(t), t
        assert check_route({"task": "youtube_search", "query": "x", "lang": "en", "goal": t}, t)["task"] == "agent"
    for t in ("search zomato", "open youtube and search for the latest indian serial analysis",
              "search how to play guitar", "YouTube లో devotional songs play చెయ్యి.", "YouTube पर भक्ति गाने चलाओ।",
              "Maps पर पास के hospitals दिखाओ।", "Chrome पर हैदराबाद का मौसम check करो।"):
        assert not beyond_search(t), t
        assert check_route({"task": "youtube_search", "query": "x", "lang": "en", "goal": t}, t)["task"] == "youtube_search"


def test_compound_requests_skip_one_task_handlers():
    from src.planner import check_route, compound
    for t in ("set an alarm for 7 am and play music", "set a timer for 5 minutes then play a song",
              "अलार्म लगाओ और गाना चलाओ", "alarm lagao aur gaana chalao"):
        assert compound(t), t
        assert check_route({"task": "alarm", "hour": 7, "minute": 0, "lang": "en", "goal": t}, t)["task"] == "agent"
    for t in ("open the clock app and set an alarm for 7 am", "set a timer for 5 minutes and 30 seconds",
              "5 मिनट और 30 सेकंड का टाइमर लगाओ", "అలారం ఉదయం ఏడు గంటలకు పెట్టు", "सुबह सात बजे का अलार्म लगाओ"):
        assert not compound(t), t


def test_shorts_only_when_asked():
    from src.safety import shorts_blocked
    assert shorts_blocked("Shorts", "play a fnaf video")
    assert shorts_blocked("FNAF clip - play Short", "play a fnaf video")
    assert not shorts_blocked("Shorts", "open youtube shorts")
    assert not shorts_blocked("Videos", "play a fnaf video")
    assert not shorts_blocked(None, "play a fnaf video")


def test_spotify_play_asks_then_plays(monkeypatch):
    from src import handlers as h
    rows = [("still alive", "lannarie", 1, 1), ("Human After All", "Daft Punk", 2, 2)]
    monkeypatch.setattr(h, "_sp_search", lambda d, q, first=False: True)
    monkeypatch.setattr(h, "_sp_songs", lambda d, want=None: rows[:])
    monkeypatch.setattr(h, "_sp_play", lambda d, row, refind=False: "played " + row[0])
    asked = []

    def conf(answers):
        c = lambda label: True
        c.reply = lambda p: (asked.append(p), answers.pop(0))[1]
        return c
    assert h.spotify_play(None, "Human After All", "Daft Punk") == "played Human After All"  # exact hit, no question
    assert h.spotify_play(None, "Human After All", "Daft Punk", dry_run=True) == "dry_run_ok"
    assert h.spotify_play(None, "Still Human", "Daft Punk") == "failed: no exact match"  # no way to ask
    assert h.spotify_play(None, "Still Human", "Daft Punk", confirm=conf(["yes"])) == "played still alive"  # top candidate
    assert "still alive" in asked[-1]
    assert h.spotify_play(None, "Still Human", "Daft Punk", confirm=conf(["no"])) == "cancelled_by_user"
    assert h.spotify_play(None, "Still Human", "Daft Punk", confirm=conf([""])) == "cancelled_by_user"
    # new song by voice: re-searched, offered again, never auto-played
    assert h.spotify_play(None, "Still Human", "x", confirm=conf(["human after all", "yes"])) == "played still alive"
