from services.group_relation_service import (
    collect_known_subgroups,
    expand_group_selection,
    labels_overlap,
    parse_group_label,
)


def test_group_labels_parse_joint_and_language_subgroups() -> None:
    joint = parse_group_label("К0109-23, К0609-23")
    subgroup = parse_group_label("К0109-23, К0609-23 (L2)")

    assert joint.base_groups == ("К0109-23", "К0609-23")
    assert joint.subgroup is None
    assert subgroup.base_groups == ("К0109-23", "К0609-23")
    assert subgroup.subgroup == "L2"


def test_experimental_selection_adds_joint_and_subgroup_labels() -> None:
    result = expand_group_selection(
        ["К0109-23"],
        [
            "К0109-23",
            "К0609-23",
            "К0109-23, К0609-23",
            "К0109-23, К0609-23 (L1)",
            "К0109-23, К0609-23 (L2)",
            "К0209-23",
        ],
    )

    assert result["base_groups"] == ["К0109-23", "К0609-23"]
    assert result["joint_groups"] == ["К0109-23, К0609-23"]
    assert result["subgroup_groups"] == [
        "К0109-23, К0609-23 (L1)",
        "К0109-23, К0609-23 (L2)",
    ]
    assert "К0209-23" not in result["selected_groups"]


def test_full_group_overlaps_subgroups_but_subgroups_do_not_overlap_each_other() -> None:
    labels = {"К0109-23", "К0109-23 (L1)", "К0109-23 (L2)"}
    known = collect_known_subgroups(labels)

    assert labels_overlap("К0109-23", "К0109-23 (L1)", known)
    assert labels_overlap("К0109-23", "К0109-23 (L2)", known)
    assert not labels_overlap("К0109-23 (L1)", "К0109-23 (L2)", known)
