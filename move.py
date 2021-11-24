# coding=utf-8

import requests
from requests.auth import HTTPBasicAuth
import re
from io import BytesIO
import urllib
import bs4

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

# For downloading Attachments!
GITLAB_OLD_USERNAME = 'user'
GITLAB_OLD_PASSWORD = 'password'

# Use a session so cookies are retained between requests.
GITLAB_OLD_SESSION = requests.session()

# IMPORTANT !!!
# make sure that user (in gitlab) has access to the project you are trying to
# import into. Otherwise the API request will fail.

# The GitLab user also has to have administrator or project owner rights
# This is required for setting specific gitlab issue ids to match with the jira ticket numbers

# gitlab old user name as key, gitlab new as value
# if you want dates and times to be correct, make sure every user is (temporarily) admin
GITLAB_USER_NAMES = {
    'gitlab-old': 'gitlab-new',
    ...
}

def login():
    # Load the login page to get a CSRF token.
    response = GITLAB_OLD_SESSION.get(
        GITLAB_OLD_URL + 'users/sign_in'
    )

    # Extract the CSRF token from the login page.
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    csrf_param = soup.find('meta', dict(name='csrf-param'))['content']
    csrf_token = soup.find('meta', dict(name='csrf-token'))['content']

    print(csrf_param)
    print(csrf_token)

    # Login.
    response = GITLAB_OLD_SESSION.post(
        response.url, 
        data={
            'user[login]': GITLAB_OLD_USERNAME,
            'user[password]': GITLAB_OLD_PASSWORD,
            csrf_param: csrf_token
        }
    )

def fetch_project_data():
    global GITLAB_OLD_PROJECT_ID
    global GITLAB_NEW_PROJECT_ID

    if not GITLAB_OLD_PROJECT_ID:
        # find out the ID of the project.
        for project in GITLAB_OLD_SESSION.get(
            GITLAB_OLD_URL + 'api/v4/projects',
            headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        ).json():
            if project['path_with_namespace'] == GITLAB_OLD_PROJECT:
                GITLAB_OLD_PROJECT_ID = project['id']
                break

    if not GITLAB_OLD_PROJECT_ID:
        raise Exception("Unable to find %s in old gitlab!" % GITLAB_PROJECT)


    # NEW GITLAB PROJECT
    if not GITLAB_NEW_PROJECT_ID:
        # find out the ID of the project.
        for project in requests.get(
            GITLAB_NEW_URL + 'api/v4/projects',
            headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN},
        ).json():
            if project['path_with_namespace'] == GITLAB_NEW_PROJECT:
                GITLAB_NEW_PROJECT_ID = project['id']
                break

    if not GITLAB_NEW_PROJECT_ID:
        raise Exception("Unable to find %s in new gitlab!" % GITLAB_NEW_PROJECT)

def fetch_old_users():
    users = GITLAB_OLD_SESSION.get(
        GITLAB_OLD_URL + 'api/v4/users?per_page=100&page=1',
        headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return users

def fetch_users():
    users = requests.get(
        GITLAB_NEW_URL + 'api/v4/users?per_page=100&page=1',
        headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return users
    
def fetch_milestones():
    milestones = requests.get(
        GITLAB_NEW_URL + 'api/v4/projects/%s/milestones' % GITLAB_NEW_PROJECT_ID,
        headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return milestones

def fetch_issues(count):
    issues = requests.get(
        GITLAB_OLD_URL + 'api/v4/projects/%s/issues?scope=all&per_page=100&page=%s' % (GITLAB_OLD_PROJECT_ID , count ),
        headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return issues

def get_assignee_id(assignee):
    if assignee == '':
        return None

    for user in users:
        if user['username'] == GITLAB_USER_NAMES.get(assignee, assignee):
            return user['id']
                
def create_milestone_for_issue(issue):
    # get milestone
    milestone_id = None

    if issue['milestone'] == None:
        return milestone_id

    exists = False
    closed = issue['milestone'].get('state') == 'closed'
    milestone_title = issue['milestone'].get('title')

    for milestone in MILESTONES:
        if milestone_title == milestone['title']:
            exists = True
            return milestone['id']

    # create if it does not exist
    if milestone_title != '' and exists == False:
        new_milestone_resp = requests.post(
            GITLAB_NEW_URL + 'api/v4/projects/%s/milestones' % GITLAB_NEW_PROJECT_ID,
            headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN},
            verify=VERIFY_SSL_CERTIFICATE,
            data={
            'title': milestone_title,
            'description': issue['milestone'].get('description'),
            'state': issue['milestone'].get('state'),
            'start_date': issue['milestone'].get('created_at'),
            'due_date': issue['milestone'].get('due_date')
            }
        )

        # returns 201 if issue was created
        if new_milestone_resp.status_code != 201:
            raise Exception(new_milestone_resp.json()['message'])
            
        new_milestone = new_milestone_resp.json()
        milestone_id = new_milestone['id']
        MILESTONES.append(new_milestone)
        
        if closed:
            update_milestone_resp = requests.put(
                GITLAB_NEW_URL + 'api/v4/projects/%s/milestones/%s' % (GITLAB_NEW_PROJECT_ID , new_milestone['id']),
                headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN},
                verify=VERIFY_SSL_CERTIFICATE,
                data={ 'state_event': 'close' }
            ).json()

    return milestone_id

def create_images_from_text(text, creator):
    # get images from description (hack)
    uploads = []
    uploads_from_desc = re.split('\[.+\]\(\/uploads\/', text)

    if len(uploads_from_desc) <= 1:
        return text
        
    for upload_in_desc in uploads_from_desc:
        if upload_in_desc == uploads_from_desc[0]:
            continue
        
        file_path = upload_in_desc[:upload_in_desc.index(")")]
        title = ""
        if match := re.search('^.*\/(.+\/)*(.+)$', file_path, re.IGNORECASE):
            title = match.group(2)

        # get attachment:
        _file = GITLAB_OLD_SESSION.get(
            GITLAB_OLD_URL + GITLAB_OLD_PROJECT + '/uploads/%s' % ( file_path ),
            headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
            verify=VERIFY_SSL_CERTIFICATE,
        )

        _content = BytesIO(_file.content)

        # upload attachment to new gitlab
        file_info = requests.post(
            GITLAB_NEW_URL + 'api/v4/projects/%s/uploads' % GITLAB_NEW_PROJECT_ID,
            headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(creator, creator)},
            files={
                'file': (
                    title,
                    _content
                )
            },
            verify=VERIFY_SSL_CERTIFICATE
        )
        
        if file_info.status_code != 201:
            print('File Upload Error: %s' % file_info.json()['message'])
            continue

        del _content

        # replace with new image path
        if match := re.search('^!{0,1}\[.*\]\((.+)*\)$', file_info.json()['markdown'], re.IGNORECASE):
            trimmed_markdown = match.group(1).replace('/uploads/', '')
            text = text.replace(file_path, trimmed_markdown)
    
    return text

def replace_gitlab_url(text):
    return text.replace(GITLAB_OLD_URL + GITLAB_OLD_PROJECT, GITLAB_NEW_URL + GITLAB_NEW_PROJECT)

def replace_user_markings(text):
    for user in old_users:
        mapped_username = GITLAB_USER_NAMES.get(user['username'], user['username'])
        text = text.replace('@%s' % user['username'], '@%s' % mapped_username)
    return text

def sync_awards(new_issue_id, old_issue_id):
    # get awards
    awards = GITLAB_OLD_SESSION.get(
        GITLAB_OLD_URL + 'api/v4/projects/%s/issues/%s/award_emoji'  % (GITLAB_OLD_PROJECT_ID , old_issue_id),
        headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    for award in awards:
        author = award['user'].get('username')

        award_add = requests.post(
            GITLAB_NEW_URL + 'api/v4/projects/%s/issues/%s/award_emoji?name=%s' % (GITLAB_NEW_PROJECT_ID, new_issue_id, award['name']),
            headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
            verify=VERIFY_SSL_CERTIFICATE
        )

def sync_awards_for_note(new_issue_id, old_issue_id, new_note_id, old_note_id):
    # get awards
    awards = GITLAB_OLD_SESSION.get(
        GITLAB_OLD_URL + 'api/v4/projects/%s/issues/%s/notes/%s/award_emoji'  % (GITLAB_OLD_PROJECT_ID , old_issue_id, old_note_id),
        headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    for award in awards:
        author = award['user'].get('username')

        award_add = requests.post(
            GITLAB_NEW_URL + 'api/v4/projects/%s/issues/%s/notes/%s/award_emoji?name=%s' % (GITLAB_NEW_PROJECT_ID, new_issue_id, new_note_id, award['name']),
            headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
            verify=VERIFY_SSL_CERTIFICATE
        )

def sync_comments(new_issue_id, old_issue_id):
    # get comments
    issue_info = GITLAB_OLD_SESSION.get(
        GITLAB_OLD_URL + 'api/v4/projects/%s/issues/%s/notes?per_page=100&page=1&sort=asc&order_by=created_at'  % (GITLAB_OLD_PROJECT_ID , old_issue_id),
        headers={'PRIVATE-TOKEN': GITLAB_OLD_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    for comment in issue_info:
        author = comment['author']['username']

        if comment['system'] == True:
            # TODO set closed by, assignee change, ...
            if comment['body'] == 'closed':
                res = requests.put(
                    GITLAB_NEW_URL + 'api/v4/projects/%s/issues/%s' % (GITLAB_NEW_PROJECT_ID , new_issue_id),
                    headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
                    verify=VERIFY_SSL_CERTIFICATE,
                    data={
                        'state_event': 'close',
                        'updated_at': comment['created_at']
                    }
                ).json()
        else:
            body = comment['body']
            body = replace_user_markings(body)
            body = replace_gitlab_url(body)
            body = create_images_from_text(body, author)

            # add comment/note
            note_add = requests.post(
                GITLAB_NEW_URL + 'api/v4/projects/%s/issues/%s/notes' % (GITLAB_NEW_PROJECT_ID, new_issue_id),
                headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
                verify=VERIFY_SSL_CERTIFICATE,
                data={
                    'body': body,
                    'created_at': comment['created_at']
                }
            )

            # returns 201 if issue was created
            if note_add.status_code != 201:
                print(note_add.json())
                continue

            new_note = note_add.json()
            sync_awards_for_note(new_issue_id, old_issue_id, new_note['id'], comment['id'])

def create_issue(issue, milestone_id):
    author = issue['author']['username']

    # get assignee user_id from new gitlab
    assignee = ''
    if issue['assignee']:
        assignee = issue['assignee'].get('username', 0)
    
    assignee_ids = []
    if issue['assignees']:
        for assign in issue['assignees']:
            user_name = assign['username']
            assignee_id = get_assignee_id(assign['username'])
            assignee_ids.append(assignee_id)
    
    labels = ""
    for label in issue['labels']:
        labels += "," + label

    description = issue['description']
    description = replace_user_markings(description)
    description = replace_gitlab_url(description)
    description = create_images_from_text(description, author)

    # create gitlab issue
    response = requests.post(
        GITLAB_NEW_URL + 'api/v4/projects/%s/issues' % GITLAB_NEW_PROJECT_ID,
        headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
        verify=VERIFY_SSL_CERTIFICATE,
        data={
            'assignee_id': get_assignee_id(assignee),
            'assignee_ids': assignee_ids,
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'description': description,
            'due_date': issue['due_date'],
            'issue_type': issue['issue_type'],
            'title': issue['title'],
            'milestone_id': milestone_id,
            'labels': labels,
            'iid': issue['iid']
        }
    )

    # returns 201 if issue was created
    if response.status_code != 201:
        # if http status = 409 there already exists an gitlab issue with this iid
        # skipping - only print response if there is an other http status
        if response.status_code != 409:
            raise Exception(response.json()['message'])
        return 0

    return response.json()['iid']

# method to set updated_at (we need a second parameter - so we use created_at)
def set_updated_at(new_issue_id, author, updated_at, created_at):
    res = requests.put(
        GITLAB_NEW_URL + 'api/v4/projects/%s/issues/%s' % (GITLAB_NEW_PROJECT_ID , new_issue_id),
        headers={'PRIVATE-TOKEN': GITLAB_NEW_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
        verify=VERIFY_SSL_CERTIFICATE,
        data={
            'created_at': created_at,
            'updated_at': updated_at
        }
    )

def sync_issues():
    count = 1
    issues = []

    # fetch all issues (needs pagination)
    while(True):
        fetched_issues = fetch_issues(count)

        if len(fetched_issues) <= 0:
            break;

        issues = issues + fetched_issues
        count += 1

    # sort issues
    issues.sort(key=lambda x: x['iid'])

    # create all issues
    for issue in issues:
        milestone_id = create_milestone_for_issue(issue)
        issue_id = create_issue(issue, milestone_id)
        
        if issue_id == 0:
            continue

        issue['new_iid'] = issue_id
        print ("created issue #%s" % issue_id)

    # create all issues
    for issue in issues:
        sync_awards(issue['new_iid'], issue['iid'])
        sync_comments(issue['new_iid'], issue['iid'])
        author = issue['author']['username']
        set_updated_at(issue['new_iid'], author, issue['updated_at'], issue['created_at'])
        print ("updated issue #%s" % issue['new_iid'])
        

login()

fetch_project_data()
users = fetch_users()
old_users = fetch_old_users()
MILESTONES = fetch_milestones()

sync_issues()
