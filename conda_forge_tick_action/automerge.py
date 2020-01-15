import os
import glob
import logging
import datetime

from ruamel.yaml import YAML
import tenacity

LOGGER = logging.getLogger(__name__)

ALLOWED_USERS = [
    'beckermr',  # TODO: remove me
    'regro-cf-autotick-bot',
]

IGNORED_STATUSES = ['conda-forge-linter']
APPVEYOR_STATUS_CONTEXT = 'continuous-integration/appveyor/pr'
IGNORED_CHECKS = ['regro-cf-autotick-bot-action']

NEUTRAL_STATES = ['pending']
BAD_STATES = ['failure', 'error']
GOOD_MERGE_STATES = ["clean", "has_hooks", "unknown", "unstable"]


@tenacity.retry(
    stop=tenacity.stop_after_attempt(10),
    wait=tenacity.wait_random_exponential(multiplier=0.1))
def _get_checks(repo, pr, session):
    return session.get(
        "https://api.github.com/repos/%s/commits/%s/check-runs" % (
            repo.full_name, pr.head.sha))


def _check_statuses(statuses, extra_ignored_statuses=None):
    extra_ignored_statuses = extra_ignored_statuses or []

    status_states = {}
    for status in statuses:
        if status.context in IGNORED_STATUSES + extra_ignored_statuses:
            continue

        if status.context not in status_states:
            # init with really old time
            status_states[status.context] = (
                None,
                datetime.datetime.now() - datetime.timedelta(weeks=10000))

        if status.state in NEUTRAL_STATES:
            if status.updated_at > status_states[status.context][1]:
                status_states[status.context] = (
                    None,
                    status.updated_at)
        elif status.state in BAD_STATES:
            if status.updated_at > status_states[status.context][1]:
                status_states[status.context] = (
                    False,
                    status.updated_at)
        else:
            if status.updated_at > status_states[status.context][1]:
                status_states[status.context] = (
                    True,
                    status.updated_at)

    for context, val in status_states.items():
        LOGGER.info('status: name|state = %s|%s', context, val[0])

    if len(status_states) == 0:
        return None, None
    else:
        if not all(val[0] for val in status_states.values()):
            return False, "PR has bad or in progress statuses"
        else:
            return True, None


def _skip_appveyor():
    fnames = glob.glob(
        os.path.join(os.environ['GITHUB_WORKSPACE'], '.ci_support', 'win*.yaml')
    )

    # windows is not on, so skip
    if len(fnames) == 0:
        return True

    # windows is on but maybe we only care about azure?
    with open(os.path.join(os.environ['GITHUB_WORKSPACE'], 'conda-forge.yml')) as fp:
        cfg = YAML().load(fp)

    # TODO double check what the smithy default is
    if cfg.get('provider', {}).get('win', None) == 'azure':
        return True

    return False


def _check_checks(checks):
    check_states = {}
    for check in checks:
        if check['name'] not in IGNORED_CHECKS:
            if check['status'] != 'completed':
                check_states[check['name']] = None
            else:
                if check['conclusion'] in BAD_STATES:
                    check_states[check['name']] = False
                else:
                    check_states[check['name']] = True

    for name, good in check_states.items():
        LOGGER.info('check: name|state = %s|%s', name, good)

    if len(check_states) == 0:
        return None, None
    else:
        if not all(v for v in check_states.values()):
            return False, "PR has failing or in progress checks"
        else:
            return True, None


def _automerge_pr(repo, pr, session):
    # only allowed users
    if pr.user.login not in ALLOWED_USERS:
        return False, "user %s cannot automerge" % pr.user.login

    # only if [bot-automerge] is in the pr title
    if '[bot-automerge]' not in pr.title:
        return False, "PR does not have the '[bot-automerge]' slug in the title"

    # now check statuses
    commit = repo.get_commit(pr.head.sha)
    statuses = commit.get_statuses()
    if _skip_appveyor():
        extra_ignored_statuses = [APPVEYOR_STATUS_CONTEXT]
    else:
        extra_ignored_statuses = None
    status_res = _check_statuses(
        statuses,
        extra_ignored_statuses=extra_ignored_statuses,
    )
    if not status_res[0] and status_res[0] is not None:
        return status_res

    # now check checks
    checks = _get_checks(repo, pr, session)
    checks_res = _check_checks(checks.json()['check_runs'])
    if not checks_res[0] and checks_res[0] is not None:
        return checks_res

    if checks_res[0] is None and status_res[0] is None:
        return False, "No checks or statuses have returned success"

    # make sure PR is mergeable and not already merged
    if pr.is_merged():
        return False, "PR has already been merged"
    if (pr.mergeable is None or
            not pr.mergeable or
            pr.mergeable_state not in GOOD_MERGE_STATES):
        return False, "PR merge issue: mergeable|mergeable_state = %s|%s" % (
            pr.mergeable, pr.mergeable_state)

    # we're good - now merge
    merge_status = pr.merge(
        commit_message="automerged PR by regro-cf-autotick-bot-action",
        commit_title=pr.title,
        merge_method='squash',
        sha=pr.head.sha)
    if not merge_status.merged:
        return (
            False,
            "PR could not be merged: message %s" % merge_status.message)
    else:
        return True, "all is well :)"


def automerge_pr(repo, pr, session):
    """Possibly automege a PR.

    Parameters
    ----------
    repo : github.Repository.Repository
        A `Repository` object for the given repo from the PyGithub package.
    pr : github.PullRequest.PullRequest
        A `PullRequest` object for the given PR from the PuGithhub package.
    session : requests.Session
        A `requests` session w/ the correct headers for the GitHub API v3.
        See `conda_forge_tick_action.api_sessions.create_api_sessions` for
        details.

    Returns
    -------
    did_merge : bool
        If `True`, the merge was done, `False` if not.
    reason : str
        The reason the merge worked or did not work.
    """
    did_merge, reason = _automerge_pr(repo, pr, session)

    if did_merge:
        LOGGER.info(
            'MERGED PR %s on %s: %s',
            pr.number, repo.full_name, reason)
    else:
        LOGGER.info(
            'DID NOT MERGE PR %s on %s: %s',
            pr.number, repo.full_name, reason)

    return did_merge, reason