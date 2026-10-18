"""Publish run-bound PR reports; never write a verdict into another run's comment."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

MARKER = '<!-- llm-release-gate-report -->'
IDENTITY = '<!-- llm-release-gate-identity '
WARNING = ('::warning::llm-release-gate could not post the PR comment '
           "(does the workflow grant 'pull-requests: write'?). "
           'The verdict is unaffected; see the job summary.')


def github_api(endpoint, *, method='GET', data=None, paginate=False):
    args = ['gh', 'api', '-X', method, endpoint]
    if paginate:
        args += ['--paginate', '--slurp']
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            text=True, encoding='utf-8', capture_output=True, check=True, timeout=30)
    return json.loads(result.stdout)


def identity_line(identity):
    return IDENTITY + json.dumps(identity, sort_keys=True) + ' -->'


def comment_identity(body):
    lines = body.splitlines()
    if len(lines) < 2 or not lines[1].startswith(IDENTITY):
        return None  # Legacy report, before head/run binding.
    identity = json.loads(lines[1][len(IDENTITY):-4])
    if (not isinstance(identity, dict) or
            any(type(identity.get(key)) is not int or identity[key] < 1
                for key in ('run', 'attempt')) or
            not isinstance(identity.get('head'), str) or
            not isinstance(identity.get('scope'), str)):
        raise ValueError('invalid report identity')
    return identity


def publish(env, api=github_api):
    repo, pr, head = env['GITHUB_REPOSITORY'], env['PR_NUMBER'], env['PR_HEAD']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not pr.isdecimal():
        raise ValueError('invalid PR identity')
    if not re.fullmatch(r'[0-9a-f]{40,64}', head):
        raise ValueError('invalid head')
    scope = hashlib.sha256(
        f"{env['REPORT_SCOPE']}:{env.get('REPORT_MATRIX', '')}".encode()).hexdigest()
    generation = (int(env['GITHUB_RUN_NUMBER']), int(env['GITHUB_RUN_ATTEMPT']))
    if min(generation) < 1 or not env['GITHUB_RUN_ID'].isdecimal():
        raise ValueError('invalid run identity')
    identity = dict(scope=scope, head=head, run=generation[0], attempt=generation[1])
    writer = 'github-actions[bot]'
    if env.get('DEFAULT_TOKEN') != 'true':
        try:
            writer = api('user')['login']
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            writer = None
    endpoint = f'repos/{repo}/issues/{pr}/comments'
    pages = api(endpoint + '?per_page=100', paginate=True)
    owned = []
    for comment in (comment for page in pages for comment in page):
        body = comment.get('body') or ''
        user = comment.get('user') or {}
        login = user.get('login') or ''
        owned_writer = (login == writer if writer is not None else
                        user.get('type') == 'Bot' and login.endswith('[bot]'))
        if (not owned_writer or
                not (body == MARKER or body.startswith(MARKER + '\n')) or
                type(comment.get('id')) is not int or comment['id'] < 1):
            continue
        try:
            previous = comment_identity(body)
        except ValueError:
            continue
        if previous is not None and previous['scope'] != scope:
            continue
        if previous is not None and (previous['run'], previous['attempt']) > generation:
            return
        owned.append((comment, previous))
    # Check immediately before publication. Isolated comment IDs also prevent a
    # head change after this read from letting an old run PATCH the newer verdict.
    if api(f'repos/{repo}/pulls/{pr}')['head']['sha'] != head:
        return
    link = (f"{env['GITHUB_SERVER_URL']}/{repo}/actions/runs/{env['GITHUB_RUN_ID']}"
            f"/attempts/{generation[1]}")
    context = f'Head: `{head}` · [Workflow run {generation[0]}, attempt {generation[1]}]({link})'
    error = env.get('GATE_EXIT_CODE') not in ('0', '1') or not env.get('REPORT_MD')
    summary = ('## llm-release-gate: unable to evaluate\n\n'
               'No verdict is available for this head. See the workflow check.')
    report = summary
    if not error:
        try:
            report = Path(env['REPORT_MD']).read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            error = True
    if not any(previous == identity for _, previous in owned):
        api(endpoint, method='POST', data={
            'body': f'{MARKER}\n{identity_line(identity)}\n\n{context}\n\n{report}'})
    # Retirement only removes older verdicts; it never publishes an old verdict
    # into a shared mutable slot. Even interleaved runs cannot overwrite a newer one.
    for comment, previous in owned:
        if previous is not None and (previous.get('retired') or
                (previous['run'], previous['attempt']) >= generation):
            continue
        metadata = '\n' + identity_line(dict(identity, retired=True))
        retired = summary if error else '## llm-release-gate: superseded\n\nSee the newer workflow report.'
        api(f"repos/{repo}/issues/comments/{comment['id']}", method='PATCH', data={
            'body': f'{MARKER}{metadata}\n\n{retired}\n\n{context}'})


def main():
    try:
        publish(os.environ)
    except Exception:
        # API/parser failures may contain credentials or evaluator text.
        print(WARNING)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
