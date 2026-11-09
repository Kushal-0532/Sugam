# STT eval (Gnani Prisma v3.0, codemix) — 2026-11-06 18:06

Clips: 30 recorded by the user (te + hi). Keyword pass (all groups hit): default config (te,hi,en auto-detect) **16/24**; language set per user (te-IN,en-IN or hi-IN,en-IN) **16/24**. STT latency p50 0.46 s, max 0.85 s (all calls).

| clip | detected (default) | hit | transcript (default) | hit (lang set) | transcript (lang set) |
|---|---|---|---|---|---|
| alarm_7am_telugu | te-IN | 2/2 | రేపు morning seven కి alarm పెట్టు. | 2/2 | రేపు morning seven కి alarm పెట్టు. |
| alarm_7am_hindi | hi-IN | 2/2 | कल सुबह सात बजे का alarm लगा दो। | 2/2 | कल सुबह सात बजे का alarm लगा दो। |
| alarm_630pm_telugu | en-IN | 3/3 | evening six thirty కి alarm set చెయ్యి. | 3/3 | evening six thirty కి alarm set చెయ్యి. |
| alarm_630pm_hindi | hi-IN | 3/3 | क्या हमको six thirty बजे का alarm set करो? | 3/3 | शाम को six thirty बजे का alarm set करो। |
| timer_5min_telugu | te-IN | 2/2 | five minutes కే timer పెట్టు. | 2/2 | five minutes కే timer పెట్టు. |
| timer_5min_hindi | hi-IN | 1/2 | इसका timer लगा दो। | 1/2 | इसका timer लगा दो। |
| calculator_telugu | en-IN | 1/1 | calculator open చేయి. | 1/1 | calculator open చెయ్యి. |
| calculator_hindi | en-IN | 1/1 | calculator open करो। | 1/1 | calculator open करो। |
| wifi_telugu | en-IN | 0/1 | if I settings open చేయి. | 0/1 | if I settings open చేయి. |
| wifi_hindi | en-IN | 1/1 | WiFi settings, Chrome. | 1/1 | WiFi settings खोलो। |
| chrome_weather_telugu | te-IN | 1/2 | Chrome లో హైదరాబాద్ మీద చూడు. | 1/2 | Chrome లో హైదరాబాద్ మీద చూడు. |
| chrome_weather_hindi | hi-IN | 2/2 | Chrome पर हैदराबाद का मौसम check करो। | 2/2 | Chrome पर हैदराबाद का मौसम check करो। |
| youtube_devotional_telugu | en-IN | 1/1 | YouTube లో devotional songs play చెయ్యి. | 1/1 | YouTube లో devotional songs play చెయ్యి. |
| youtube_devotional_hindi | te-IN | 1/1 | YouTube పై భక్తి కానీ చలో. | 1/1 | YouTube पर भक्ति गाने चलाओ। |
| maps_hospital_telugu | te-IN | 1/2 | slot దగ్గరలో ఉన్న hospitals చూపించు. | 1/2 | slot దగ్గరలో ఉన్న hospitals చూపించు. |
| maps_hospital_hindi | hi-IN | 2/2 | Maps पर पास के hospitals दिखाओ। | 2/2 | Maps पर पास के hospitals दिखाओ। |
| maps_pharmacy_telugu | te-IN | 1/2 | నా దగ్గరలో medical shops ఎక్కడ ఉందో చూపించు. | 1/2 | నా దగ్గరలో medical shops ఎక్కడ ఉందో చూపించు. |
| maps_pharmacy_hindi | hi-IN | 1/2 | मेरे पास कोई pharmacy तो नहीं है? | 1/2 | मेरे पास कोई pharmacy ढूंढ दो। |
| call_amma_telugu | te-IN | 3/3 | Test అమ్మకి call చెయ్యి. | 3/3 | Test అమ్మకి call చెయ్యి. |
| call_amma_hindi | te-IN | 1/3 | Stamco call కరువు. | 1/3 | stump को call करो। |
| msg_papa_telugu | te-IN | 2/3 | నేను తిన్నానని test అన్నానికి message పెట్టు. | 2/3 | నేను తిన్నానని test అన్నానికి message పెట్టు. |
| msg_papa_hindi | hi-IN | 3/3 | Test Papa को message भेजा कि मैंने खाना खा लिया। | 3/3 | Test Papa को message भेजा कि मैंने खाना खा लिया। |
| paytm_block_telugu | te-IN | 1/1 | Paytm open చేసి money పంపించు. | 1/1 | Paytm open చేసి money పంపించు. |
| paytm_block_hindi | hi-IN | 1/1 | Paytm call कर, पैसे भेजो। | 1/1 | Paytm call कर पैसे भेजो। |

Control clips (scored by tests/test_safety.py, not here). Plain = codemix + 3 langs + app keyterms (the command config); `@gate` = safety.gate_stt (task language locked + answer-word keyterms):

- confirm_yes_telugu: `Open now.` [en-IN]
- confirm_yes_hindi: `ఆ.` [te-IN]
- confirm_no_telugu: `కాదు.` [te-IN]
- confirm_no_hindi: `नहीं।` [hi-IN]
- stop_telugu: `App.` [en-IN]
- stop_hindi: `रुको।` [hi-IN]
- confirm_yes_telugu@gate: `అవును.` [te]
- confirm_yes_hindi@gate: `हाँ।` [hi]
- confirm_no_telugu@gate: `కాదు.` [te]
- confirm_no_hindi@gate: `नहीं।` [hi]
- stop_telugu@gate: `ఆపు.` [te]
- stop_hindi@gate: `रुको।` [hi]
