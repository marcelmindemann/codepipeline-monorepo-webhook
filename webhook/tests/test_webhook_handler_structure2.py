import json
import os

import pytest

from ..exceptions import NotListeningOnBranchError, NoFilesTouchedError, NoSubfoldersFoundError
from ..handler import get_event_body, check_branch, get_touched_files, get_unique_subfolders, prefix_subfolders


@pytest.fixture
def webhook_fixture():
  path = f"{os.path.dirname(os.path.abspath(__file__))}/webhook_fixture_structure2.json"

  os.environ['BRANCH_ROUTE'] = "false"
  os.environ["BRANCH_ROUTES"] = '["master"]'
  os.environ['PROJECT_SERVICE_MODEL'] = "nested"
  os.environ['PROJECT_PREFIX_REPO'] = "false"
  os.environ['PROJECT_PREFIX_PARENT'] = 'true'

  with open(path, 'r') as input:
    event = json.load(input)
    event['body'] = json.dumps(event['body'])
    return get_event_body(event)

@pytest.mark.xfail(raises=NotListeningOnBranchError, strict=True)
def test_check_branch_fails(webhook_fixture):
  os.environ["BRANCH_ROUTES"] = '["fail"]'
  check_branch(webhook_fixture)


def test_check_branch(webhook_fixture):
  assert check_branch(webhook_fixture)


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
  assert touched_files[0] == 'service1/folder1/added.py'
  assert touched_files[1] == 'service1/folder2/removed.py'
  assert touched_files[2] == 'service2/folder3/modified.py'


@pytest.mark.xfail(raises=NoSubfoldersFoundError, strict=True)
def test_get_unique_subfolders_fails():
  touched_files = ['README.md']
  get_unique_subfolders(touched_files)


def test_get_unique_subfolders(webhook_fixture):
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  assert len(subfolders) == 3
  assert subfolders.__contains__("service1/folder1")
  assert subfolders.__contains__("service1/folder2")
  assert subfolders.__contains__("service2/folder3")

def test_get_prefix_subfolders(webhook_fixture):
  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('service1-folder1')
  assert codepipeline_names.__contains__('service1-folder2')
  assert codepipeline_names.__contains__('service2-folder3')

def test_get_prefix_subfolders_with_repo_name(webhook_fixture):
  os.environ['PROJECT_PREFIX_REPO'] = "true"

  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service1-folder1')
  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service1-folder2')
  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service2-folder3')

def test_get_prefix_subfolders_with_branch_routing_prefix(webhook_fixture):
  os.environ['BRANCH_ROUTE'] = "prefix"
  os.environ["BRANCH_ROUTES"] = '{"master": "prod"}'

  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('prod-service1-folder1')
  assert codepipeline_names.__contains__('prod-service1-folder2')
  assert codepipeline_names.__contains__('prod-service2-folder3')

def test_get_prefix_subfolders_with_branch_routing_postfix(webhook_fixture):
  os.environ['BRANCH_ROUTE'] = "postfix"
  os.environ["BRANCH_ROUTES"] = '{"master": "prod"}'

  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('service1-folder1-prod')
  assert codepipeline_names.__contains__('service1-folder2-prod')
  assert codepipeline_names.__contains__('service2-folder3-prod')

def test_get_prefix_subfolders_with_repo_name_branch_routing_prefix(webhook_fixture):
  os.environ['BRANCH_ROUTE'] = "prefix"
  os.environ["BRANCH_ROUTES"] = '{"master": "prod"}'
  os.environ['PROJECT_PREFIX_REPO'] = "true"

  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('prod-codepipeline-monorepo-webhook-service1-folder1')
  assert codepipeline_names.__contains__('prod-codepipeline-monorepo-webhook-service1-folder2')
  assert codepipeline_names.__contains__('prod-codepipeline-monorepo-webhook-service2-folder3')

def test_get_prefix_subfolders_with_repo_name_branch_routing_postfix(webhook_fixture):
  os.environ['BRANCH_ROUTE'] = "postfix"
  os.environ["BRANCH_ROUTES"] = '{"master": "prod"}'
  os.environ['PROJECT_PREFIX_REPO'] = "true"

  repository_name = 'codepipeline-monorepo-webhook'
  touched_files = get_touched_files(webhook_fixture)
  subfolders = get_unique_subfolders(touched_files)
  branch_route = check_branch(webhook_fixture)
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service1-folder1-prod')
  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service1-folder2-prod')
  assert codepipeline_names.__contains__('codepipeline-monorepo-webhook-service2-folder3-prod')