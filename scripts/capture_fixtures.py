"""Capture hierarchy fixtures. Only launches apps and reads the UI tree: no taps, no typing."""
import time, uiautomator2 as u2

SCREENS = {  # name -> package (None = home screen)
    "home": None,
    "clock": "com.oneplus.deskclock",
    "youtube": "com.google.android.youtube",
    "settings": "com.android.settings",
    "dialer": "com.google.android.dialer",
}
d = u2.connect()
for name, pkg in SCREENS.items():
    d.press("home") if pkg is None else d.app_start(pkg, use_monkey=True)
    time.sleep(3)
    xml = d.dump_hierarchy()
    open(f"tests/fixtures/{name}.xml", "w").write(xml)
    print(f"{name:9} fg={d.app_current()['package']:32} {len(xml):7} bytes")
d.press("home")
