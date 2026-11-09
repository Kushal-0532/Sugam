import glob
import os
from src.screen import compact, CAP

FX = os.path.join(os.path.dirname(__file__), "fixtures")
load = lambda n: open(f"{FX}/{n}.xml", encoding="utf-8").read()


def test_all_fixtures_capped_and_ids_sequential():
    for p in glob.glob(f"{FX}/*.xml"):
        els, h, pkg = compact(open(p, encoding="utf-8").read())
        assert 0 < len(els) <= CAP, p
        assert [e["id"] for e in els] == list(range(len(els)))
        assert pkg and h


def test_hash_stable_and_differs():
    a, b = load("clock"), load("settings")
    assert compact(a)[1] == compact(a)[1]
    assert compact(a)[1] != compact(b)[1]


def test_no_invisible_or_zero_area():
    xml = ('<hierarchy><node bounds="[0,0][100,100]" package="p" visible-to-user="true" class="x">'
           '<node text="ghost" visible-to-user="false" bounds="[0,0][50,50]" package="p"/>'
           '<node text="flat" visible-to-user="true" bounds="[10,10][10,50]" package="p"/>'
           '<node text="real" visible-to-user="true" bounds="[0,0][50,50]" package="p"/></node></hierarchy>')
    assert [e["text"] for e in compact(xml)[0]] == ["real"]


def test_label_merge():
    xml = ('<hierarchy><node package="p" bounds="[0,0][100,100]" visible-to-user="true">'
           '<node clickable="true" class="LinearLayout" bounds="[0,0][100,50]" visible-to-user="true" package="p">'
           '<node text="Alarm" bounds="[0,0][50,50]" visible-to-user="true" package="p" class="TextView"/></node>'
           '</node></hierarchy>')
    els = compact(xml)[0]
    assert len(els) == 1 and els[0]["text"] == "Alarm" and els[0]["click"]


def test_real_clock_has_labels():
    els = compact(load("clock"))[0]
    assert any(e["click"] and (e["text"] or e["desc"]) for e in els)


def test_elements_under_a_bar_are_dropped():
    def node(bounds, label="", click="true", pkg="app", kids=""):
        return (f'<node package="{pkg}" class="android.widget.Button" text="{label}" content-desc="" resource-id="" '
                f'clickable="{click}" scrollable="false" visible-to-user="true" bounds="{bounds}">{kids}</node>')
    xml = ("<hierarchy>" + node("[200,900][400,1000]", "Home", pkg="com.android.systemui")
           + node("[0,0][600,1000]", "root", "false", kids=(
               node("[0,0][600,200]", "visible row", kids=node("[500,50][550,100]", "row menu"))
               + node("[0,700][600,900]", "row behind bar")
               + node("[0,850][600,1000]", "row behind home")
               + node("[0,750][300,850]", "bar tab") + node("[300,750][600,850]", "bar tab 2")))
           + "</hierarchy>")
    labels = [e["text"] for e in compact(xml, size=(600, 1000))[0]]
    assert "visible row" in labels and "row menu" in labels and "bar tab" in labels  # own child is not a cover
    assert "row behind bar" not in labels and "row behind home" not in labels


def test_scrolling_out_from_under_a_bar_changes_the_hash():
    a = '<node package="app" class="B" text="row" clickable="true" visible-to-user="true" bounds="[0,800][600,1000]"/>'
    b = '<node package="app" class="B" text="row" clickable="true" visible-to-user="true" bounds="[0,400][600,600]"/>'
    bar = '<node package="app" class="B" text="bar" clickable="true" visible-to-user="true" bounds="[0,850][600,1000]"/>'
    size = (600, 1000)
    assert compact(f"<hierarchy>{a}{bar}</hierarchy>", size=size)[1] != compact(f"<hierarchy>{b}{bar}</hierarchy>", size=size)[1]
