from scs.probe import (
    ext_bytes,
    file_listing,
    is_not_found,
    parse_object_sizes,
    parse_tree,
    readme_oid,
)

LS_TREE = (
    "100644 blob aaa\tREADME.md\n"
    "100644 blob bbb\tsrc/train.py\n"
    "100644 blob ccc\tassets/fig.PNG\n"
    "160000 commit ddd\tthird_party/sub\n"
    "100644 blob eee\tdocs/readme.txt\n"
)
BATCH_CHECK = "aaa blob 1200\nbbb blob 8000\nfff tree 75\n"


def test_parse_tree_skips_submodules():
    files = parse_tree(LS_TREE)
    assert files == {
        "README.md": "aaa",
        "src/train.py": "bbb",
        "assets/fig.PNG": "ccc",
        "docs/readme.txt": "eee",
    }


def test_ext_bytes_counts_missing_blobs_as_limit():
    files = parse_tree(LS_TREE)
    sizes = parse_object_sizes(BATCH_CHECK)
    # ccc、eee 没有下载内容，按上限 1000 计
    assert ext_bytes(files, sizes, missing_size=1000) == {
        ".md": 1200,
        ".png": 1000,
        ".py": 8000,
        ".txt": 1000,
    }


def test_readme_only_at_root():
    assert readme_oid(parse_tree(LS_TREE)) == "aaa"
    assert readme_oid({"docs/README.md": "x"}) == ""


def test_not_found_detection():
    assert is_not_found(
        "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    )
    assert is_not_found("remote: Repository not found.")
    assert not is_not_found("fatal: unable to access: Could not resolve host: github.com")


def test_file_listing_sorted_with_unknown_sizes():
    listing = file_listing(parse_tree(LS_TREE), parse_object_sizes(BATCH_CHECK))
    assert listing == (
        ("README.md", 1200),
        ("assets/fig.PNG", -1),
        ("docs/readme.txt", -1),
        ("src/train.py", 8000),
    )
