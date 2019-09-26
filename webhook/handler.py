import hmac
import json
import logging
import os
from urllib.parse import unquote
import json

import boto3

from .exceptions import NoSignatureError, NotListeningOnBranchError, NoSubfoldersFoundError, \
    InvalidSignatureError, NoFilesTouchedError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def calculate_message_signature(key: str, msg: str):
  """
  calculate a message signature using a SHA1 HMAC
  :param key: the secret token
  :param msg: the message
  :return: the calculated HMAC
  """
  return hmac.new(key.encode(), msg=msg.encode(), digestmod='sha1').hexdigest()

def check_github_message_signature(event: dict, webhook_secret: str) -> bool:
  """
  check if supplied message signature is valid
  :param event: GitHub webhook request
  :param webhook_secret: the secret token
  :return: True if message signature is valid
  """
  if 'X-Hub-Signature' not in event['headers']:
    raise NoSignatureError()

  supplied_sig = event['headers']['X-Hub-Signature'].split('=')[1]
  logger.info(f'Supplied message signature: {supplied_sig}')
  calculated_sig = calculate_message_signature(webhook_secret, event['body'])
  logger.info(f'Calculated message signature: {calculated_sig}')

  # check message authentication
  if hmac.compare_digest(supplied_sig, calculated_sig):
    logger.info('Valid message signature found. Request is authenticated.')
    return True
  else:
    raise InvalidSignatureError()

def get_event_body(event: dict) -> dict:
  """
  extract event body from url-encoded request
  :param event: GitHub webhook request
  :return: dict holding the event body
  """
  event_body = json.loads(event['body'])
  logger.debug(f'Parsed event body: {json.dumps(event_body, default=str)}')
  return event_body

def check_branch(event_body: dict) -> bool:
  """
  check if this webhook should care about the pushed branch
  :param event_body: dict holding the event body
  :param target_branch: which branch to care about
  :return: True if pushed branch is worthy of attention
  """
  pushed_branch = event_body['ref']
  logger.info(f'Pushed branch: {pushed_branch}')

  branches = json.loads(os.environ["BRANCH_ROUTES"])

  for branch in branches:
    target_branch = f'refs/heads/{branch}'

    if pushed_branch == target_branch:
      logger.info(f'Target branch: {branch}')
      return branches[branch] if type(branches) is dict else True
  
  raise NotListeningOnBranchError(pushed_branch)

def get_touched_files(event_body: dict) -> list:
  """
  extract list of added, removed and modified files with full paths from webhook request
  :param event_body: dict holding the event body
  :return: list of touched files
  """
  touched_files = []

  # look at every touched file in every commit
  for commit in event_body['commits']:
    touched_files.extend(commit['added'])
    touched_files.extend(commit['removed'])
    touched_files.extend(commit['modified'])

  touched_files.extend((event_body['head_commit']['added']))
  touched_files.extend((event_body['head_commit']['removed']))
  touched_files.extend((event_body['head_commit']['modified']))

  if len(touched_files) > 0:
    return touched_files
  else:
    raise NoFilesTouchedError()

def get_unique_subfolders(touched_files: list) -> set:
  """
  extract set of folders that the touched files sit in
  :param touched_files: list of touched files with full paths
  :return: set of folder names
  """
  subfolders = []
  
  if os.environ["PROJECT_SERVICE_MODEL"] == 'split':
    # Get the unique top-level directories
    subfolders = set(
      [splitted[0] for splitted in
        (file.split('/') for file in
        touched_files)
        if len(splitted) > 1]
    )
  elif os.environ["PROJECT_SERVICE_MODEL"] == 'nested':
    # Get the unique second-level directories
    subfolders = set(
      ['/'.join(splitted[:-1:]) for splitted in
        (file.split('/') for file in
        touched_files)
        if len(splitted) > 1]
    )
  elif os.environ["PROJECT_SERVICE_MODEL"] == 'combined':
    # Get the unique top-level directories
    subfolders = set(
      ['/'.join(splitted).split('.')[0] for splitted in
        (file.split('/') for file in
        touched_files)
        if len(splitted) > 1]
    )

  elif os.environ["PROJECT_SERVICE_MODEL"] == 'full':
    # Get the unique third-level directories
    subfolders = set(
      ['/'.join(splitted[1:-1:]) for splitted in
        (file.split('/') for file in
        touched_files)
        if len(splitted) > 1]
    )

  if len(subfolders) > 0:
    logger.info(f'Subfolders found: {subfolders}.')
    return subfolders
  else:
    raise NoSubfoldersFoundError()

def prefix_subfolders(subfolders: set, repo_prefix: str, branch_route: str) -> list:
  """
  prefix folder names with a string, joining with dash
  :param subfolders: set of folder names
  :param prefix: the prefix to use
  :return: list of prefixed folders
  """
  prefixed_subfolders = []
  repo_prefix = repo_prefix + "-" if os.environ["PROJECT_PREFIX_REPO"] == 'true' else ""

  for subfolder in subfolders:
    project_name = subfolder.split('/')[0] if os.environ["PROJECT_SERVICE_MODEL"] == 'nested' or os.environ["PROJECT_SERVICE_MODEL"] == 'combined' or os.environ["PROJECT_SERVICE_MODEL"] == 'full' else ''
    subfolder = subfolder.split('/')[len(subfolder.split('/'))-1]
    project_name = project_name + "-" if len(project_name) > 0 and os.environ["PROJECT_PREFIX_PARENT"] == 'true' else ""

    if os.environ["BRANCH_ROUTE"] == 'prefix':
        prefixed_subfolders.append(f'{branch_route}-{repo_prefix}{project_name}{subfolder}')
    elif os.environ["BRANCH_ROUTE"] == 'postfix':
        prefixed_subfolders.append(f'{repo_prefix}{project_name}{subfolder}-{branch_route}')
    else:
      prefixed_subfolders.append(f'{repo_prefix}{project_name}{subfolder}')
  
  return prefixed_subfolders

def start_codepipelines(codepipeline_names: list) -> dict:
  """
  start AWS CodePipelines
  :param codepipeline_names: the CodePipelines to start
  :return: dict holding the results of the start operations
  """
  codepipeline_client = boto3.Session().client('codepipeline')

  failed_codepipelines = []
  started_codepipelines = []
  for codepipeline_name in codepipeline_names:
    try:
      codepipeline_client.start_pipeline_execution(
          name=codepipeline_name
      )
      logger.info(f'Started CodePipeline {codepipeline_name}.')
      started_codepipelines.append(codepipeline_name)
    except codepipeline_client.exceptions.PipelineNotFoundException:
      logger.info(f'Could not find CodePipeline {codepipeline_name}.')
      failed_codepipelines.append(codepipeline_name)

  if len(failed_codepipelines) > 0:
    return {
      'statusCode': 502,
      'body': f'Started CodePipelines {started_codepipelines}. \nCould not start CodePipelines {failed_codepipelines}.'
    }
  else:
    return {
      'statusCode': 200,
      'body': f'Started CodePipelines {started_codepipelines}.'
    }

def handle(event, context):
  """
  triggers codepipelines for commits in subfolders of the data-ingestion monorepo
  :param event: HTTP POST event, triggered by GitHub webhook
  :param context: lambda context
  :return: nothing
  """

  webhook_secret = os.environ['GITHUB_WEBHOOK_SECRET']
  logger.info('---- CHECKING MESSAGE AUTHENTICATION ----')
  try:
    check_github_message_signature(event, webhook_secret)
  except (NoSignatureError, InvalidSignatureError) as err:
    logger.error(err.error_dict['body'])
    return err.error_dict

  if event['headers']['X-GitHub-Event'] == 'ping':
    return {
      'statusCode': 200,
      'body': 'Ping received.'
    }

  github_delivery_id = event['headers']['X-GitHub-Delivery']
  logger.info(f'Webhook handler invoked for Github delivery id {github_delivery_id}.')

  logger.info('---- PARSING WEBHOOK PAYLOAD ----')
  event_body = get_event_body(event)
  branch_route = None
  try:
    branch_route = check_branch(event_body)
  except NotListeningOnBranchError as err:
    logger.error(err.error_dict['body'])
    return {
      'statusCode': 202,
      'body': f'Not started any CodePipelines. Not listening on branch {event_body["ref"]}.'
    }

  try:
    touched_files = get_touched_files(event_body)
  except NoFilesTouchedError as err:
    logger.error(err.error_dict['body'])
    return {
      'statusCode': 202,
      'body': f'Not started any CodePipelines. No files have been changed'
    }

  try:
    subfolders = get_unique_subfolders(touched_files)
  except NoSubfoldersFoundError as err:
    logger.error(err.error_dict['body'])
    return {
      'statusCode': 202,
      'body': f'Not started any CodePipelines. No subfolders found.'
    }

  logger.info('---- STARTING RESPECTIVE CODEPIPELINES ----')
  repository_name = event_body['repository']['name']
  codepipeline_names = prefix_subfolders(subfolders, repository_name, branch_route)

  if 'isOffline' not in event or not event['isOffline']:
    return start_codepipelines(codepipeline_names)
  else:
    return {
      'statusCode': 200,
      'body': f'Currently offline, but the pipelines are: {codepipeline_names}.'
    }