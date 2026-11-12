"""Rewards rules that need no database: catalogue, art, odds, pity and the points arithmetic."""
import random
import xml.dom.minidom

import game
import game_items as items


def test_catalogue_is_large_regular_and_every_rarity_has_items():
    assert len(items.CATALOG) > 2000
    assert all(items.BY_RARITY[r] for r in range(len(items.RARITIES)))
    assert len({i["id"] for i in items.CATALOG.values()}) == len(items.CATALOG)
    assert {i["slot"] for i in items.CATALOG.values()} == set(items.SLOTS)


def test_shop_sells_only_the_cheaper_rarities():
    assert all(i["shop"] == (i["rarity"] <= items.SHOP_MAX_RARITY) for i in items.CATALOG.values())
    assert items.CATALOG["hat.cap.red"]["price"] == 15 and not items.CATALOG["hat.crown.rainbow"]["shop"]


def test_art_is_valid_svg_for_a_sample_of_items_and_ignores_bad_outfits():
    for item_id in random.Random(1).sample(sorted(items.CATALOG), 120):
        xml.dom.minidom.parseString(items.item_svg(item_id))
    svg = items.avatar_svg({"hat": "hat.crown.gold", "top": "hat.crown.gold", "pet": "nope"}, "cocoa")
    xml.dom.minidom.parseString(svg)
    assert svg.count("<svg") == 1


def test_every_style_draws_on_both_bodies_with_no_placeholder_left():
    for slot, styles in items.STYLES.items():
        for style in styles:
            item_id = f"{slot}.{style}.rainbow"
            pictures = [items.item_svg(item_id)] + ([items.avatar_svg({slot: item_id}, build=build) for build in items.BUILDS] if slot in items.WORN else [])
            for svg in pictures:
                xml.dom.minidom.parseString(svg)
                assert "@" not in svg and "|||" not in svg, item_id


def test_small_pictures_are_head_and_shoulders_and_hats_flatten_tall_hair():
    whole, bust = items.avatar_svg({}, "sand"), items.avatar_svg({}, "sand", crop="bust")
    assert 'viewBox="0 0 200 300"' in whole and f'viewBox="{items.BUST}"' in bust
    assert items.avatar_svg({}, "sand", crop="nonsense") == whole
    bun = items.avatar_svg({"hair": "hair.bun.red"})
    assert len(items.avatar_svg({"hair": "hair.bun.red", "hat": "hat.halo.gold"})) > len(bun)                 # an open hat keeps the bun
    assert "<circle" in bun and len(items.hair_layers("hair.bun.red", crest=False)[0]) < len(items.hair_layers("hair.bun.red")[0])


def test_art_renders_as_png_where_cairo_is_installed():
    import pytest
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("cairo is not installed here")
    for svg in (items.avatar_svg({"hair": "hair.afro.galaxy", "top": "top.kimono.rainbow", "back": "back.backpack.holo", "held": "held.flask.green", "pet": "pet.owl.brown"}, "tan", build="feminine"),
                items.avatar_svg({}, crop="bust"), items.item_svg("hat.wizard.galaxy"), items.item_svg("held.balloon.red"), items.item_svg("trinket.planet.blue")):
        assert items.png(svg, 96)[1:4] == b"PNG"


def test_pity_forces_a_rare_and_an_epic():
    rng = random.Random(3)
    assert all(game.roll_rarity(rng, game.RARE_PITY - 1, 0) >= 2 for _ in range(200))
    assert all(game.roll_rarity(rng, 0, game.EPIC_PITY - 1) >= 3 for _ in range(200))
    state = {"pulls": 0, "since_rare": 0, "since_epic": 0}
    best = [items.CATALOG[game.pull_once(rng, state)]["rarity"] for _ in range(300)]
    assert state["pulls"] == 300 and max(best) >= 3
    gaps, run = [], 0
    for rarity in best:
        run = 0 if rarity >= 2 else run + 1
        gaps.append(run)
    assert max(gaps) < game.RARE_PITY


def test_odds_are_roughly_the_published_ones():
    rng = random.Random(11)
    counts = [0] * 6
    for _ in range(20000):
        counts[game.roll_rarity(rng, 0, 0)] += 1
    assert 0.52 < counts[0] / 20000 < 0.58 and counts[5] > 0


def test_points_arithmetic():
    stats = dict(review_correct=10, achieved=2, merit=1, excellence=1, lessons=3, papers_achieved=1, papers_merit=0, papers_excellence=1, days=4)
    total, lines = game.earnings(stats)
    assert total == 50 + 8 + 6 + 8 + 75 + 60 + 160 + 40 == sum(line["points"] for line in lines)
    assert game.earnings({k: 0 for k in stats})[0] == 0


def test_paper_grade_uses_the_apps_bands():
    assert [game.paper_grade(a, 100) for a in (49, 50, 70, 85)] == ["not_achieved", "achieved", "merit", "excellence"]
    assert game.paper_grade(0, 0) is None


def test_gpa_scale_and_grade_names():
    assert [game.gpa_from(m) for m in (0, 0.4, 0.6, 0.8, 1, 2)] == [0, 3, 5, 7, 9, 9]
    assert game.gpa_from(0.5) == 4.0
    assert [game.grade_name(m) for m in (0.3, 0.5, 0.7, 0.9)] == ["Not achieved", "Achieved", "Merit", "Excellence"]


def test_networth_counts_every_copy_and_ignores_retired_items():
    assert game.networth(100, {"hat.cap.red": 2, "gone.item.x": 5}) == 100 + 2 * 10
