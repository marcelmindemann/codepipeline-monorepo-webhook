# codepipeline-monorepo-webhook
A webhook handler that triggers AWS CodePipelines for mono repos, implemented as a serverless AWS Lambda function.

## Why
If you are building a big application consisting of multiple microservices, or you are building a data crunching application with loads of data ingestion pipelines, you probably want to use a mono repo.
Until now, this has been a pain to build properly with AWS CodePipeline, because CodePipeline still doesn't support mono repos, even though this feature has been requested [for over two years](https://forums.aws.amazon.com/thread.jspa?threadID=265045).
Let's say your application is structured like this:
```
mono-repo/
├── microservice-1/
│   ├── buildspec.yml
│   ├── handler.js
│   └── README.md
├── microservice-2/
│   ├── buildspec.yml
│   └── main.py
│ ...
```
When a commit changes files in `microservice-1`, you only want to build this specific folder, not the whole repository (this can take a long time and get expensive with a big mono repo). 
The CodePipeline WebhookFilterRule is insufficient when trying to model this workflow, because it does [not allow for regex matching](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codepipeline-webhook-webhookfilterrule.html).
Strangely, the [Code*Build* WebhookFilter does support it](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_WebhookFilter.html).

To solve this problem, create a CodePipeline for every microservice/subrepo that exists in your application and let this webhook figure out which CodePipelines need to be started.

## Deployment
You will need [Poetry](https://poetry.eustace.io/), serverless and npm. Run
```bash
poetry install --no-dev
npm install
```
to install the required dependencies. 

The webhook handler needs a secret string `GithubSecret` in the AWS Parameter Store to authenticate the GitHub requests.

To deploy to AWS, run
```bash
serverless deploy --env prd
```

Add the URL of the Lambda function to your mono repo on Github via _Settings - Webhook - Add webhook_. Add the value of `GithubSecet` to the webhook under _Secret_.

Check if everything works as expected by looking at the response to the initial ping request sent by GitHub. If the response says 'Ping received', the webhook handler is ready. To debug problems, first look at the response to the webhook request, it'll inform you which CodePipelines have been started and which CodePipelines could not be found. For more in-depth debugging, look at the Cloudwatch logs for the lambda function.

## Configuration
There are two configuration options:

* `target_branch`: Which branch the webhook handler should listen on. If this is set to `master`, and GitHub triggers the webhook with a request containing commits on `feature/add-logging`, the request will be dismissed.
* `prefix_repo_name`: If set to `true`, the name of the mono repo is prepended to the names of the subfolders when building the names of CodePipelines to start. Using the example directory structure from above:
  * `prefix_repo_name` is `true`: CodePipeline `mono-repo-microservice-1` will be started.
  * `prefix_repo_name` is `false`: CodePipeline `microservice-1` will be started.
  
## Development
Pull requests are welcome. To start development, install the dev dependencies with
```bash
poetry install
```
Run tests with
```bash
poetry run pytest
```
