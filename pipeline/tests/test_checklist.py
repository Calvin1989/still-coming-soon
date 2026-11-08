from datetime import date

import pytest

from scs import checklist as cl
from scs import config, store
from scs.build import build_venue
from scs.models import Paper, RepoLink, RepoSnapshot
from scs.render_parts import entry, legend

README = """
# Project
## TODO
- [x] Release inference code
- [ ] Release **training** code
* [X] Release [checkpoints](https://huggingface.co/x)
1. [ ] Release the dataset
- [ ] ~~Release the fine-tuning code~~ See the new repo
<!--
- [ ] Release secret code
-->
Not a task: [ ] Release nothing
"""


def test_extract_tasks():
    assert cl.extract_tasks(README) == (
        (True, "Release inference code"),
        (False, "Release **training** code"),
        (True, "Release [checkpoints](https://huggingface.co/x)"),
        (False, "Release the dataset"),
        (False, "~~Release the fine-tuning code~~ See the new repo"),
    )


@pytest.mark.parametrize(
    "text",
    [
        "Release the training code.",
        "Release pre-trained weights and inference code.",
        "Open-source the Xplore-Agent model",
        "Upload zero-shot evaluation scripts.",
        "Training code",
        "Checkpoints",
        "Pretraining Code (expected before Chinese New Year)",
        "Release [code](https://example.com)",
        "Training dataset release.",
    ],
)
def test_release_items(text):
    assert cl.is_release_item(text)


@pytest.mark.parametrize(
    "text",
    [
        "Release paper",  # 论文本身
        "Release project page",
        "~~Release the checkpoints of the Lookahead VLN Model.~~",  # 划掉了
        "Release code on more datasets",  # 扩展计划
        "Release the new version of checkpoints, which is trained with more data",
        "Evaluation code for other datasets.",
        "Support training on more datasets",
        "Scale up the model size (based on LLaMA3)",
        "feat: add model loading methods.",
        "Provide a runnable encode/decode example",
        "Dataset preparation and installation guidance",  # 说的是文档
        "Datasets are easier to use",
        "Gradio demo for relative camera pose regression",
        "Code for ViT-Lens integration with InstructBLIP and SEED",
        "Code for nuPlan dataset (3D Occupancy Prediction)",
        "Code for the nuScenes dataset (coming soon)",
        "Source code of CIDM with SD XL version",
        "Release weights training with addtional data",
        "Dataset-specific modeling details for paper",
    ],
)
def test_not_release_items(text):
    assert not cl.is_release_item(text)


def test_kinds():
    assert cl.kinds_of("Release the training and inference code") == ("training", "inference")
    assert cl.kinds_of("Release pre-trained weights") == ("weights",)
    assert cl.kinds_of("Release pretrained checkpoints") == ("weights",)
    assert cl.kinds_of("Training dataset release") == ("training", "data")
    assert cl.kinds_of("Release the SynRS3D generation code") == ("code",)


def test_file_kinds():
    assert cl.file_kinds(["train.py", "README.md"]) == ("training",)
    assert cl.file_kinds(["scripts/finetune.sh", "tools/infer.py"]) == ("training", "inference")
    assert cl.file_kinds(["training/main.py"]) == ("training",)
    assert cl.file_kinds(["pretrained/README.md", "constraint.py"]) == ()


def test_present_kinds():
    readme = (
        "Weights: https://huggingface.co/org/model-7b . Data: https://huggingface.co/datasets/org/d"
    )
    assert cl.present_kinds(["train.py"], readme) == ("training", "weights", "data")
    # Hugging Face 上的 Space、论文页不算下载链接
    assert cl.present_kinds([], "demo at huggingface.co/spaces/org/demo") == ()
    assert cl.present_kinds([], "see https://github.com/org/repo") == ()


def test_summarize():
    c = cl.summarize(cl.extract_tasks(README))
    assert (c.done, c.total) == (2, 4)
    assert c.open == ("Release training code", "Release the dataset")
    assert c.open_kinds == ("training", "data")
    # 仓库里已经有训练代码：没勾的训练项当作作者忘了勾
    c = cl.summarize(cl.extract_tasks(README), present=("training",))
    assert (c.done, c.open) == (3, ("Release the dataset",))
    # 笼统的"某某代码"不属于四类核心内容，不算
    assert cl.summarize([(False, "Release the code for efficiency analysis")]) is None
    # 只有扩展计划或者没有清单：没有可说的
    assert cl.summarize([(False, "Support more datasets")]) is None
    assert cl.summarize([]) is None


def test_snapshot_roundtrip(tmp_path):
    snaps = [
        RepoSnapshot(
            "a/b",
            "2026-11-08T00:00:00",
            True,
            tasks=((False, "Release code"),),
            present_kinds=("training",),
        ),
        RepoSnapshot("c/d", "2026-11-08T00:00:00", True),
    ]
    store.save_snapshots("v", snaps, tmp_path)
    text = (tmp_path / "snapshots" / "v.jsonl").read_text(encoding="utf-8")
    assert '"tasks"' in text.splitlines()[0] and '"tasks"' not in text.splitlines()[1]
    assert store.load_snapshots("v", tmp_path) == snaps


def _site(snap):
    cfg = config.load()
    paper = Paper("arxiv:1", "iclr2025", "T", "u", "2025-01-01", "")
    links = [RepoLink("arxiv:1", snap.repo, (snap.repo,))]
    return build_venue(
        cfg.venues["iclr2025"], [paper], links, [snap], cfg.classify, date(2026, 11, 8)
    )


def test_build_and_render_checklist():
    tasks = cl.extract_tasks(README)
    released = RepoSnapshot("a/b", "2026-11-08", True, ext_bytes={".py": 50_000}, tasks=tasks)
    site = _site(released)
    row = site["rows"][0]
    assert row["status"] == "released" and site["checklist_open"] == 1
    assert row["checklist"]["open"] == ["Release training code", "Release the dataset"]
    t = {
        "status": {"released": "Code released"},
        "checklist_note": "{done} of {total} ticked:",
        "checklist_legend": "Checklist not finished",
    }
    html = entry(row, t, None)
    assert 'data-extra="checklist"' in html and "<li>Release the dataset</li>" in html
    assert "2 of 4 ticked:" in html
    assert 'data-statuses="checklist" aria-pressed="false"' in legend({}, t, checklist=1)
    # 空仓库已经算没兑现，不再加清单说明；主状态不受清单影响
    empty = RepoSnapshot("a/b", "2026-11-08", True, tasks=tasks)
    site = _site(empty)
    assert site["rows"][0]["status"] == "empty" and "checklist" not in site["rows"][0]
    assert site["checklist_open"] == 0
