"""Offline API boundary for the Action's comment publisher."""

import copy
import importlib.util
from pathlib import Path


def load_reporter():
    path = Path(__file__).resolve().parents[1] / 'scripts/post_pr_comment.py'
    spec = importlib.util.spec_from_file_location('post_pr_comment', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGithub:
    def __init__(self, head='a' * 40):
        self.head = head
        self.comments = []
        self.calls = []
        self.before_post = None
        self.writer = 'github-actions[bot]'

    def add(self, body, login='github-actions[bot]'):
        comment = {'id': len(self.comments) + 1, 'body': body, 'user': {'login': login}}
        self.comments.append(comment)
        return comment

    def __call__(self, endpoint, *, method='GET', data=None, paginate=False):
        self.calls.append((endpoint, method, data, paginate))
        if endpoint == 'user':
            return {'login': self.writer}
        if endpoint == 'repos/owner/repo/pulls/7':
            return {'head': {'sha': self.head}}
        if endpoint == 'repos/owner/repo/issues/7/comments?per_page=100':
            assert paginate
            comments = copy.deepcopy(self.comments)
            return [comments[i:i + 100] for i in range(0, len(comments), 100)]
        if method == 'POST' and endpoint == 'repos/owner/repo/issues/7/comments':
            if self.before_post:
                callback, self.before_post = self.before_post, None
                callback()
            return self.add(data['body'], login=self.writer)
        if method == 'PATCH':
            prefix = 'repos/owner/repo/issues/comments/'
            assert endpoint.startswith(prefix)
            comment_id = endpoint[len(prefix):]
            assert comment_id.isdecimal() and '\n' not in comment_id
            comment = next(c for c in self.comments if c['id'] == int(comment_id))
            comment['body'] = data['body']
            return comment
        raise AssertionError(f'unexpected API call: {method} {endpoint}')


def invocation(tmp_path, *, head='a' * 40, run=1, attempt=1):
    report = tmp_path / f'report-{run}-{attempt}.md'
    report.write_text('## llm-release-gate: **PASS**\n', encoding='utf-8')
    return dict(GITHUB_REPOSITORY='owner/repo', PR_NUMBER='7', PR_HEAD=head,
                GITHUB_RUN_NUMBER=str(run), GITHUB_RUN_ATTEMPT=str(attempt),
                GITHUB_RUN_ID=str(1000 + run), GITHUB_SERVER_URL='https://github.com',
                REPORT_SCOPE='CI:gate:release-gate', DEFAULT_TOKEN='true',
                REPORT_MD=str(report), GATE_EXIT_CODE='0')
