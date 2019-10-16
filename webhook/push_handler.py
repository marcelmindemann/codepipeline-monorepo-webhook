
import os
import logging

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