import os
import requests
import urllib3.util.retry

from github import Github


def create_api_sessions(github_token):
    # based on
    #  https://alexwlchan.net/2019/03/
    #    creating-a-github-action-to-auto-merge-pull-requests/
    # with lots of edits
    sess = requests.Session()
    sess.headers = {
        "Accept": "; ".join([
            "application/vnd.github.v3+json",
            # special beta api for chck_run endpoint
            "application/vnd.github.antiope-preview+json",
        ]),
        "Authorization": f"token {github_token}",
        "User-Agent": f"GitHub Actions script in {__file__}"
    }

    def raise_for_status(resp, *args, **kwargs):
        try:
            resp.raise_for_status()
        except Exception as e:
            print('ERROR:', resp.text)
            raise e

    sess.hooks["response"].append(raise_for_status)

    # build a github object too
    gh = Github(
        os.environ["INPUT_REPO-TOKEN"],
        retry=urllib3.util.retry.Retry(total=10, backoff_factor=0.1))

    return sess, gh
