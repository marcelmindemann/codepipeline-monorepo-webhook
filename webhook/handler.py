import hmac
import json
import logging
import os
from urllib.parse import unquote

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
    event_body = json.loads(unquote(event['body']).replace('payload=', ''))
    logger.debug(f'Parsed event body: {json.dumps(event_body, default=str)}')
    return event_body


def check_branch(event_body: dict, target_branch: str) -> bool:
    """
    check if this webhook should care about the pushed branch
    :param event_body: dict holding the event body
    :param target_branch: which branch to care about
    :return: True if pushed branch is worthy of attention
    """
    target_branch = f'refs/heads/{target_branch}'
    pushed_branch = event_body['ref']
    logger.info(f'Pushed branch: {pushed_branch}')
    logger.info(f'Target branch: {target_branch}')

    if pushed_branch == target_branch:
        return True
    else:
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
    # extract unique top-level directories from all the paths of touched files
    subfolders = set(
        [splitted[0] for splitted in
         (file.split('/') for file in
          touched_files)
         if len(splitted) > 1]
    )

    if len(subfolders) > 0:
        logger.info(f'Subfolders found: {subfolders}.')
        return subfolders
    else:
        raise NoSubfoldersFoundError()


def prefix_subfolders(subfolders: set, prefix: str) -> list:
    """
    prefix folder names with a string, joining with dash
    :param subfolders: set of folder names
    :param prefix: the prefix to use
    :return: list of prefixed folders
    """
    return [f'{prefix}-{subfolder}' for subfolder in subfolders]


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
            response = codepipeline_client.start_pipeline_execution(
                name=codepipeline_name
            )
            logger.info(f'Started CodePipeline {codepipeline_name}.')
            started_codepipelines.append(codepipeline_name)
        except codepipeline_client.exceptions.PipelineNotFoundException:
            logger.info(f'Could not find CodePipeline {codepipeline_name}.')
            failed_codepipelines.append(codepipeline_name)

    if len(failed_codepipelines) > 0:
        return {
            'statusCode': 500,
            'body': f'Started CodePipelines {started_codepipelines}. \nCould not start CodePipelines {failed_codepipelines}.'
        }
    else:
        return {
            'statusCode': 200,
            'body': f'Started CodePipelines {started_codepipelines}.'
        }


def main(event, context):
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
    try:
        target_branch = os.environ["TARGET_BRANCH"]
        check_branch(event_body, target_branch)
    except NotListeningOnBranchError as err:
        logger.error(err.error_dict['body'])
        return err.error_dict

    try:
        touched_files = get_touched_files(event_body)
    except NoFilesTouchedError as err:
        logger.error(err.error_dict['body'])
        return err.error_dict

    try:
        subfolders = get_unique_subfolders(touched_files)
    except NoSubfoldersFoundError as err:
        logger.error(err.error_dict['body'])
        return err.error_dict

    logger.info('---- STARTING RESPECTIVE CODEPIPELINES ----')
    prefix_repo_name = os.environ['PREFIX_REPO_NAME'] == 'true'
    if prefix_repo_name:
        repository_name = event_body['repository']['name']
        logger.info(f'Prefixing CodePipelines with repository name: {repository_name}.')
        codepipeline_names = prefix_subfolders(subfolders, repository_name)
    else:
        logger.info('Not prefixing CodePipelines with repository name.')
        codepipeline_names = subfolders

    return start_codepipelines(codepipeline_names)
