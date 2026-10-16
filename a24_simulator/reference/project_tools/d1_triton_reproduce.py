"""Explicit fresh replay in a separate folder; never reset the original budget."""
import argparse
from pathlib import Path
from tools import d1_triton_study as s


def run(folder):
    folder = Path(folder).resolve()
    original = s.ROOT / 'output/external_rules_20261007_v2'
    if (folder == original.resolve() or folder.parent != (s.ROOT / 'output').resolve()
            or not folder.name.startswith('external_rules_20261007_')):
        raise ValueError('use a separate output/external_rules_20261007_* directory')
    if folder.exists() and any(folder.iterdir()) and not (folder / 'reproduction_session.json').exists():
        raise ValueError('nonempty directory is not an owned reproduction session')
    folder.mkdir(parents=True, exist_ok=True)
    registration = folder / 'reproduction_session.json'
    if registration.exists():
        session = s.read(registration)
    else:
        session = dict(start_utc=s.stamp(), reason='explicit new replay; original campaign consumption preserved',
                       original_contract_sha256=s.digest(s.BUNDLE / 'contract.json'),
                       wrapper_sha256=s.digest(Path(__file__)), environment_budget=400)
        s.write(registration, session)
        users = [x for x in s.ROOT.iterdir() if x.is_file() and x.suffix.lower() in ('.html', '.pdf')]
        users += [x for x in (s.ROOT / '.vscode').rglob('*') if x.is_file()]
        for tree in s.ROOT.glob('*_files'):
            users += [x for x in tree.rglob('*') if x.is_file()]
        s.write(folder / 'preserved_user_files.json', {x.relative_to(s.ROOT).as_posix(): s.digest(x) for x in users})
    if (session['wrapper_sha256'] != s.digest(Path(__file__)) or
            session['original_contract_sha256'] != s.digest(s.BUNDLE / 'contract.json')):
        raise ValueError('replay provenance drift')
    s.LOCAL = folder
    s.START = session['start_utc']
    return s.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    args = parser.parse_args()
    run(args.folder)
