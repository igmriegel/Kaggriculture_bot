import json

from agent.analysis.replays import audit_replays, write_audit


def test_audit_extracts_leader_daily_economy_and_writes_artifacts(tmp_path) -> None:
    replay = {
        "info": {
            "EpisodeId": 7,
            "seed": 11,
            "Agents": [{"Name": "Ryo Hasegawa"}, {"Name": "other"}],
        },
        "rewards": [1200, 900],
        "steps": [
            [
                {
                    "observation": {
                        "day": 0,
                        "farms": [
                            {
                                "money": 3000,
                                "hands": [],
                                "unlocked_quadrants": ["NW"],
                                "tiles": [[None]],
                            }
                        ],
                    },
                    "action": {
                        "farmer": ["PASS"],
                        "hands": [],
                        "market": [["BUY_ANIMAL", "COW", 1]],
                    },
                },
                {},
            ],
            [
                {
                    "observation": {
                        "day": 1,
                        "farms": [
                            {
                                "money": 2800,
                                "hands": [],
                                "unlocked_quadrants": ["NW"],
                                "tiles": [[{"kind": "PASTURE", "animal": "COW"}]],
                            }
                        ],
                    },
                    "action": {"farmer": ["CARE"], "hands": [], "market": []},
                },
                {},
            ],
        ],
    }
    source = tmp_path / "replay.json"
    source.write_text(json.dumps(replay), encoding="utf-8")

    report = audit_replays([source])
    episode = report["episodes"][0]

    assert episode["leader_score"] == 1200
    assert episode["days"][0]["order_units"] == {"BUY_ANIMAL:COW": 1}
    assert episode["days"][1]["animals"] == {"COW": 1}
    json_path, markdown_path = write_audit(report, tmp_path / "audit")
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert "Episode 7" in markdown_path.read_text(encoding="utf-8")
