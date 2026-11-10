#!/usr/bin/python3
"""Prepare and execute the explicitly authorized twelve-run paired study.

The two frozen product drivers retain ownership of campaign execution/recovery.
This controller owns only pairing, fixed inputs, final selection and confirmation.
Credentials remain outside the reproducibility snapshot and are never printed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = Path('/tmp/competition-skill-refactor-20261110/ml-env/bin/python')
CODEX = Path('/home/lzh/.local/node-v24.20.0/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex')
STUDY = Path('/home/lzh/workspace/competition-agent-validation/paired-20261110')
PREPARED = {
    'maxcut': Path('/tmp/competition-paired-eval-20261110/maxcut/prepared'),
    'energy': Path('/tmp/competition-paired-eval-20261110/energy/prepared-final'),
}
TERMINAL = {'complete', 'blocked', 'stopped_by_user', 'limit_reached'}
THREADS = {key: '1' for key in ('OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS',
           'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
           'BLIS_NUM_THREADS', 'RAYON_NUM_THREADS')}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise ValueError('A frozen input must not contain symlinks: ' + str(path))
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def copy_tree(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))
    if tree(source) != tree(target):
        raise ValueError('Snapshot read-back differs: ' + str(target))


def checked(command, log, *, cwd=None, env=None, timeout=300):
    started = time.monotonic()
    with Path(log).open('w') as stream:
        process = subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                                 stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if process.returncode:
        raise RuntimeError(f'Command exited {process.returncode}; inspect {log}')
    return time.monotonic() - started


def environment(seed):
    return {**os.environ, **THREADS, 'PYTHONHASHSEED': str(seed), 'PYTHONDONTWRITEBYTECODE': '1'}


def schedule(cores):
    if len(cores) < 2:
        raise ValueError('This paired protocol requires two distinct available CPU cores')
    jobs = []
    for repetition, seed in enumerate((11, 29, 47)):
        for task in ('maxcut', 'energy'):
            pair = f'{task}-s{seed}'
            for index, arm in enumerate(('old', 'new')):
                jobs.append({'id': f'{pair}-{arm}', 'pair': pair, 'task': task, 'arm': arm,
                             'seed': seed, 'repetition': repetition + 1,
                             'cpu': cores[(index + repetition) % 2], 'max_wall_seconds': 1800})
    return jobs


def minimal_config(original, workspace):
    """Serialize only the selected provider plus fixed settings; never log it."""
    provider = original.get('model_providers', {}).get('my_codex')
    if not isinstance(provider, dict):
        raise ValueError('The configured my_codex provider is missing')
    lines = ['model = "gpt-6-astra"', 'model_provider = "my_codex"',
             'model_reasoning_effort = "max"', 'approval_policy = "never"',
             'sandbox_mode = "workspace-write"', 'web_search = "disabled"']

    def table(name, values):
        lines.extend(['', '[' + '.'.join(json.dumps(key) for key in name) + ']'])
        for key, value in values.items():
            if not isinstance(value, dict):
                lines.append(json.dumps(key) + ' = ' + json.dumps(value))
        for key, value in values.items():
            if isinstance(value, dict):
                table([*name, key], value)

    table(['model_providers', 'my_codex'], provider)
    table(['projects', str(workspace)], {'trust_level': 'trusted'})
    rendered = '\n'.join(lines) + '\n'
    tomllib.loads(rendered)
    return rendered


def paths(root, job):
    base = root / 'jobs' / job['id']
    return {'base': base, 'workspace': base / 'workspace', 'campaign': base / 'campaign',
            'archive': base / 'workspace/archive.jsonl', 'home': base / 'codex-home',
            'skill': root / 'versions' / job['arm'],
            'public': root / 'tasks' / job['task'] / 'public',
            'private': root / 'tasks' / job['task'] / 'private'}


def task_prompt(root, job, python):
    p = paths(root, job)
    return f'''# Fixed paired-workflow optimization task

Use the competition-optimize skill at {p['skill']}/SKILL.md and read its
relevant references. Read {p['public']}/TASK.md for the task contract.
Your task seed is {job['seed']}. Improve the declared development objective
through implemented algorithm/model changes and executed evaluations.

Working directory: {p['workspace']}
Existing archive: {p['archive']}
Baseline run: {p['workspace']}/runs/baseline
Editable starting implementation: {p['workspace']}/candidate.py
Skill scripts: {p['skill']}/scripts
Python with the fixed task dependencies: {python}

Use this common evaluator with a new output directory for each implementation:
{python} -B {p['public']}/task.py evaluate --public {p['public']} --candidate candidate.py --output runs/NAME --seed {job['seed']}

Read the returned archive.source, archive.configuration and archive.result.
Record experiments with your skill's candidate_archive.py CLI. Energy archive
source is the OOF CSV and configuration is recipe.json; Max-Cut archive source
is the executed candidate.py. Keep the baseline and accepted run files intact.
Use the skill's proposal, evaluation and feedback workflow. After an archived
implementation/evaluation step, return the driver's required structured receipt
so the outer loop can continue. Continue within the controller's 30-minute
window; there is no requested candidate count, parameter sweep or score target.

Public task files, evaluator, folds, seeds and data are fixed. Do not edit them
or change the comparison contract. Use only the provided development data and
locally available dependencies. Do not access web/network, install packages,
read credentials or another job's files, seek private confirmation data, or
use external precomputed solutions. Confirmation occurs only after the
controller freezes the selected implementation and is never returned to you.
Do not submit to any platform. Do not modify the campaign runner or control
files. Failed experiments and unfinished hypotheses must be preserved honestly.
'''


def evaluate_command(python, public, candidate, output, seed):
    return [python, '-B', public / 'task.py', 'evaluate', '--public', public,
            '--candidate', candidate, '--output', output, '--seed', str(seed)]


def prepare(root, *, repo=REPO, python=PYTHON, codex=CODEX, prepared=PREPARED):
    root, repo, python, codex = (Path(x).resolve() for x in (root, repo, python, codex))
    if root.exists():
        raise ValueError('Study directory already exists; inspect/resume it instead of preparing again')
    # Validate dependencies before creating any study state; no model calls.
    for path in (python, codex, Path.home() / '.codex/config.toml', Path.home() / '.codex/auth.json'):
        if not path.is_file():
            raise ValueError('Required local dependency is absent: ' + str(path))
    original = tomllib.loads((Path.home() / '.codex/config.toml').read_text())
    minimal_config(original, root)
    version = subprocess.check_output([str(codex), '--version'], text=True).strip()
    cores = sorted(os.sched_getaffinity(0))[:2]
    jobs = schedule(cores)
    root.mkdir(parents=True, mode=0o700)
    for name in ('versions', 'tasks', 'jobs', 'secrets', 'controller', 'results'):
        (root / name).mkdir(mode=0o700)
    prefix = 'skills/competition-optimize/'
    archive = subprocess.check_output(['git', 'archive', '80331a1', prefix], cwd=repo)
    old = root / 'versions/old'
    old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as package:
        for member in package.getmembers():
            if member.isfile() and member.name.startswith(prefix):
                relative = Path(member.name[len(prefix):])
                if '..' in relative.parts or relative.is_absolute():
                    raise ValueError('Unsafe source archive member')
                target = old / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.extractfile(member).read())
                target.chmod(member.mode & 0o777)
            elif member.issym() or member.islnk():
                raise ValueError('Skill snapshot must not contain archive links')
    copy_tree(repo / 'skills/competition-optimize', root / 'versions/new')
    for task, source in prepared.items():
        copy_tree(source, root / 'tasks' / task)
    copy_tree(HERE, root / 'controller/paired')
    versions = {arm: tree(root / 'versions' / arm) for arm in ('old', 'new')}
    inputs = {'versions': versions, 'tasks': {task: tree(root / 'tasks' / task) for task in prepared},
              'controller': tree(root / 'controller/paired')}
    write(root / 'inputs.json', inputs)
    protocol = {'schema_version': 1, 'created_at': now(), 'old_git_commit': '80331a1',
                'new_version': 'uncommitted working-tree byte snapshot; see inputs.json',
                'model': 'gpt-6-astra', 'reasoning_effort': 'max', 'model_provider': 'my_codex',
                'codex_path': str(codex), 'codex_version': version, 'codex_sha256': digest(codex),
                'python': str(python), 'cores': cores, 'jobs': jobs,
                'pairing': 'Six sequential pairs, two arms concurrent; task seeds matched, model RNG not exposed',
                'budget': '1800 wall seconds per campaign, including retries/backoff; no count/token cap',
                'excluded_from_optimization_timer': ['task preparation', 'baseline evaluation', 'post-freeze confirmation'],
                'selection': 'Best verified comparable development objective; baseline then earliest on exact ties',
                'confirmation': 'Freeze entire selected run; one trusted confirmation; no model feedback or refit',
                'failures': 'Retain every scheduled run and failure; no discarded or silently replaced repetitions',
                'analysis': 'Per-task paired outcomes; no pooled raw-score average or mechanism-causality claim',
                'sources': {'maxcut': 'tasks/maxcut/sources.json', 'energy': 'tasks/energy/public/sources.json'},
                'inputs_sha256': digest(root / 'inputs.json')}
    write(root / 'protocol.json', protocol)
    for job in jobs:
        p = paths(root, job)
        for name in ('base', 'workspace', 'home'):
            p[name].mkdir(mode=0o700)
        (p['workspace'] / 'runs').mkdir()
        shutil.copyfile(p['public'] / 'candidate.py', p['workspace'] / 'candidate.py')
        (p['base'] / 'task.md').write_text(task_prompt(root, job, python))
        secret = root / 'secrets' / (job['id'] + '.toml')
        secret.write_text(minimal_config(original, p['workspace']))
        secret.chmod(0o600)
        launcher = p['base'] / 'agent-launcher'
        shutil.copyfile(HERE / 'agent_launcher.py', launcher)
        launcher.chmod(0o755)
        config = {'codex_path': str(codex), 'codex_sha256': protocol['codex_sha256'],
                  'codex_version': version, 'model': protocol['model'], 'reasoning_effort': 'max',
                  'model_provider': 'my_codex', 'cpu_affinity': [job['cpu']],
                  'python_hash_seed': job['seed'], 'job_id': job['id'],
                  'log_path': str(p['base'] / 'launcher-events.jsonl'), 'codex_home': str(p['home']),
                  'isolation': {'hidden_roots': ['/home/lzh/workspace', '/tmp', str(Path.home() / '.codex')],
                    'read_only': [str(p['skill']), str(p['public']), str(python.parent.parent),
                      {'source': str(Path.home() / '.codex/auth.json'), 'target': str(p['home'] / 'auth.json')},
                      {'source': str(secret), 'target': str(p['home'] / 'config.toml')}],
                    'writable': [str(p['workspace']), str(p['campaign']), str(p['home'])]}}
        write(p['base'] / 'launcher-config.json', config)
        baseline = p['workspace'] / 'runs/baseline'
        elapsed = checked(['taskset', '-c', str(job['cpu']),
                           *evaluate_command(python, p['public'], p['workspace'] / 'candidate.py', baseline, job['seed'])],
                          p['base'] / 'baseline-evaluation.log', env=environment(job['seed']))
        result = read(baseline / 'result.json')
        if result.get('valid') is not True or result['score']['value'] is None:
            raise ValueError('Baseline did not produce a valid score: ' + job['id'])
        source = baseline / ('oof.csv' if job['task'] == 'energy' else 'candidate.py')
        record = ['/usr/bin/python3', '-B', p['skill'] / 'scripts/candidate_archive.py', 'record',
                  '--archive', p['archive'], '--candidate-id', 'baseline', '--source', source,
                  '--result', baseline / 'result.json', '--route', 'provided-baseline',
                  '--mechanism', 'Fixed common baseline supplied before optimization', '--status', 'incumbent']
        if job['task'] == 'energy':
            record += ['--configuration', baseline / 'recipe.json']
        checked(record, p['base'] / 'baseline-archive.log', env=environment(job['seed']))
        entries = [json.loads(line) for line in p['archive'].read_text().splitlines()]
        write(p['base'] / 'baseline-entry.json', entries[0])
        copy_tree(baseline, p['base'] / 'baseline-backup')
        write(p['base'] / 'prepared.json', {'job': job, 'at': now(), 'baseline_score': result['score'],
              'baseline_seconds': elapsed, 'baseline_files': tree(baseline),
              'task_sha256': digest(p['base'] / 'task.md'), 'launcher_sha256': digest(launcher),
              'launcher_config_sha256': digest(p['base'] / 'launcher-config.json'),
              'provider_config_sha256': digest(secret)})
        print(json.dumps({'prepared': job['id'], 'baseline': result['score']['value']}), flush=True)
    write(root / 'state.json', {'status': 'prepared', 'at': now(), 'completed': []})
    return protocol


def verify_inputs(root, protocol):
    if digest(root / 'inputs.json') != protocol['inputs_sha256']:
        raise ValueError('The frozen input manifest changed')
    expected = read(root / 'inputs.json')
    for arm, files in expected['versions'].items():
        if tree(root / 'versions' / arm) != files:
            raise ValueError('Frozen skill bytes changed: ' + arm)
    for task, files in expected['tasks'].items():
        if tree(root / 'tasks' / task) != files:
            raise ValueError('Frozen task bytes changed: ' + task)
    if tree(root / 'controller/paired') != expected['controller']:
        raise ValueError('Frozen controller bytes changed')
    for job in protocol['jobs']:
        p = paths(root, job)
        expected_job = read(p['base'] / 'prepared.json')
        for name, filename in [('task_sha256', 'task.md'), ('launcher_sha256', 'agent-launcher'),
                               ('launcher_config_sha256', 'launcher-config.json')]:
            if digest(p['base'] / filename) != expected_job[name]:
                raise ValueError('Job launch input changed: ' + job['id'] + '/' + filename)
        if digest(root / 'secrets' / (job['id'] + '.toml')) != expected_job['provider_config_sha256']:
            raise ValueError('Job provider configuration changed: ' + job['id'])


def campaign_command(root, job, operation):
    p = paths(root, job)
    command = ['/usr/bin/python3', '-B', p['skill'] / 'scripts/autonomous_campaign.py', operation,
               '--campaign', p['campaign']]
    if operation == 'start':
        command += ['--workspace', p['workspace'], '--archive', p['archive'],
                    '--task-file', p['base'] / 'task.md', '--agent-bin', p['base'] / 'agent-launcher',
                    '--model', 'gpt-6-astra', '--sandbox', 'workspace-write',
                    '--max-wall-seconds', str(job['max_wall_seconds']),
                    '--turn-timeout-seconds', str(job['max_wall_seconds'])]
    if operation in ('start', 'resume'):
        command += ['--background']
    return command


def launch(root, job):
    p = paths(root, job)
    state_path = p['campaign'] / 'state.json'
    if state_path.exists():
        return read(state_path)  # Recovery uses native resume, never a second start.
    checked(campaign_command(root, job, 'start'), p['base'] / 'launch.log',
            cwd=p['workspace'], env=environment(job['seed']), timeout=30)
    return read(state_path)


def status(root, protocol):
    jobs = []
    for job in protocol['jobs']:
        p = paths(root, job)
        state = read(p['campaign'] / 'state.json') if (p['campaign'] / 'state.json').exists() else {}
        jobs.append({'id': job['id'], 'status': state.get('status', 'not_started'),
                     'turn': state.get('turn_number', 0), 'progress': state.get('progress'),
                     'elapsed_seconds': round(time.time() - state['created_unix'], 1) if state and state.get('status') not in TERMINAL else None,
                     'agent_seconds': state.get('agent_seconds', 0), 'usage': state.get('usage', {}),
                     'best': state.get('objective_progress', {}).get('best_value')})
    return {'study': str(root), 'jobs': jobs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'run', 'status', 'finalize', 'stop'])
    parser.add_argument('--study', type=Path, default=STUDY)
    args = parser.parse_args()
    root = args.study.resolve()
    if args.operation == 'prepare':
        prepare(root)
    else:
        protocol = read(root / 'protocol.json')
        if args.operation == 'status':
            print(json.dumps(status(root, protocol), ensure_ascii=False, indent=2))
        elif args.operation == 'stop':
            write(root / 'stop.json', {'at': now(), 'reason': 'Explicit controller stop'})
            for job in protocol['jobs']:
                p = paths(root, job)
                if (p['campaign'] / 'state.json').exists() and read(p['campaign'] / 'state.json')['status'] not in TERMINAL:
                    checked([*campaign_command(root, job, 'stop'), '--now'], p['base'] / 'stop.log')
        else:
            raise NotImplementedError('Execution/confirmation integration is being completed before model launch')


if __name__ == '__main__':
    main()
