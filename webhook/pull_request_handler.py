import os
import logging
import boto3
import json
import requests

from .exceptions import NoSignatureError, NotListeningOnBranchError, NoSubfoldersFoundError, \
    InvalidSignatureError, NoFilesTouchedError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_touched_files(event_body: dict) -> list:
  """
  extract list of added, removed and modified files with full paths from webhook request
  :param event_body: dict holding the event body
  :return: list of touched files
  """
  touched_files = []

  url = event_body['pull_request']['_links']['commits']['href']
  commits = requests.get(url, auth=('',os.environ['GITHUB_ACCESS_TOKEN'])).json()
  
  # look at every touched file in every commit
  for commit_info in commits:
    commit_url = commit_info['url']
    commit = requests.get(commit_url, auth=('',os.environ['GITHUB_ACCESS_TOKEN'])).json()

    for file_desc in commit['files']:
      touched_files.append(file_desc['filename'])

  if len(touched_files) > 0:
    return touched_files
  else:
    raise NoFilesTouchedError()

def handle_pipelines(event, pipelines, branch):
  cp_client = boto3.client('codepipeline')

  handled_pipelines = []

  for pipeline in pipelines:
    pipeline_info = cp_client.get_pipeline(name=pipeline)
    actions = pipeline_info['pipeline']['stages'][0]['actions']
    
    for i, action in enumerate(actions):
      if action['name'] == 'Source':
        pipeline_info['pipeline']['stages'][0]['actions'][i]['configuration']['Branch'] = branch

    cp_client.update_pipeline(pipeline=pipeline_info['pipeline'])
    handled_pipelines.append(pipeline_info['pipeline']['name'])

  return handled_pipelines
