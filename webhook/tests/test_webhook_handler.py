import json
import os

import pytest

from ..exceptions import NotListeningOnBranchError, NoFilesTouchedError, NoSubfoldersFoundError
from ..handler import check_branch, get_touched_files, get_unique_subfolders


@pytest.fixture
def webhook_fixture():
    path = f"{os.path.dirname(os.path.abspath(__file__))}/webhook_fixture.json"
    with open(path, 'r') as input:
        return json.load(input)


@pytest.mark.xfail(raises=NotListeningOnBranchError, strict=True)
def test_check_branch_fails(webhook_fixture):
    check_branch(webhook_fixture, "fail")


def test_check_branch(webhook_fixture):
    check_branch(webhook_fixture, "target-branch")


@pytest.mark.xfail(raises=NoFilesTouchedError, strict=True)
def test_get_touched_files_fails():
    event_body = {
        'commits': [{
            'added': [],
            'removed': [],
            'modified': []
        }],
        'head_commit': {
            'added': [],
            'removed': [],
            'modified': []
        }
    }
    get_touched_files(event_body)


def test_get_touched_files(webhook_fixture):
    touched_files = get_touched_files(webhook_fixture)
    assert len(touched_files) == 3
    assert touched_files[0] == 'folder1/added.py'
    assert touched_files[1] == 'folder2/removed.py'
    assert touched_files[2] == 'folder3/modified.py'


@pytest.mark.xfail(raises=NoSubfoldersFoundError, strict=True)
def test_get_unique_subfolders_fails():
    touched_files = ['README.md']
    get_unique_subfolders(touched_files)


def test_get_unique_subfolders(webhook_fixture):
    touched_files = get_touched_files(webhook_fixture)
    subfolders = get_unique_subfolders(touched_files)
    assert len(subfolders) == 3
    assert subfolders.__contains__("folder1")
    assert subfolders.__contains__("folder2")
    assert subfolders.__contains__("folder3")
