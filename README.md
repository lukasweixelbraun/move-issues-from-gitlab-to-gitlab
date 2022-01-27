# Move Issues from Gitlab to Gitlab
Python 3 Script for moving issues from one gitlab to another.

## How to use

Make sure that the gitlab user is assigned to your gitlab project and exists in the user mapping inside the Script. 

The user has to be an ***Owner***. This is required for setting specific gitlab_issue_ids to match with the previous ticket numbers.

Before you start the Script make sure you have set all the variables inside the script:


```python
GITLAB_NEW_URL = 'https://gitlab.example.com/'
# this token will be used whenever the API is invoked
GITLAB_NEW_TOKEN = 'your-access-token-new-gitlab'
# the project in gitlab that you are importing issues to.
GITLAB_NEW_PROJECT = 'gitlab-group/gitlab-project'
# the numeric project ID. If you don't know it, the script will search for it
# based on the project name.
GITLAB_NEW_PROJECT_ID = 1
# set this to false if Gitlab is using self-signed certificate.
VERIFY_SSL_CERTIFICATE = True

# same for the new gitlab
GITLAB_OLD_URL = 'https://gitlab.example-old.com/'
GITLAB_OLD_TOKEN = 'your-access-token-old-gitlab'
GITLAB_OLD_PROJECT = 'gitlab-group/gitlab-project'
GITLAB_OLD_PROJECT_ID = 2

# Your gitlab credentials for downloading Attachments
GITLAB_OLD_USERNAME = 'user'
GITLAB_OLD_PASSWORD = 'password'

# Use a session so cookies are retained between requests.
GITLAB_OLD_SESSION = requests.session()

GITLAB_USER_NAMES = {
    'gitlab-old': 'gitlab-new',
    ...
}

...

```

<br>

## User Mapping

It can happen, that the Jira username and the gitlab username are not the same. To fix this you can define an username_mapping on the top of the script.
