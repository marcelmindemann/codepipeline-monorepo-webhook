class LambdaError(Exception):
    def __init__(self, error_dict: dict):
        self.error_dict = error_dict


class NoSignatureError(LambdaError):
    def __init__(self):
        self.error_dict = {
            'statusCode': 401,
            'body': 'No X-Hub-Signature in HTTP header.'
        }


class InvalidSignatureError(LambdaError):
    def __init__(self):
        self.error_dict = {
            'statusCode': 401,
            'body': 'Message signature is invalid.'
        }


class NotListeningOnBranchError(LambdaError):
    def __init__(self, pushed_branch):
        self.error_dict = {
            'statusCode': 422,
            'body': f'Not listening on branch {pushed_branch}.'
        }


class NoFilesTouchedError(LambdaError):
    def __init__(self):
        self.error_dict = {
            'statusCode': 422,
            'body': 'No files have been touched in commit.'
        }


class NoSubfoldersFoundError(LambdaError):
    def __init__(self):
        self.error_dict = {
            'statusCode': 422,
            'body': 'No subfolders found.'
        }


class NoSuchPipelineError(LambdaError):
    def __init__(self, codepipeline_name):
        self.error_dict = {
            'statusCode': 422,
            'body': f'Cannot find CodePipeline {codepipeline_name}.'
        }
