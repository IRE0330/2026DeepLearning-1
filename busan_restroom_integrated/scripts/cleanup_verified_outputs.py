"""Remove only archived byte duplicates and wheel-verified install/build copies."""
import json
import os
from pathlib import Path
import shutil
import zipfile
from consolidate_final import ROOT, fs, safe, sha


def main():
    outputs, pkg = ROOT / 'outputs', ROOT / 'cctv-analysis'
    final = outputs / 'final'
    if (final / 'cleanup_report.json').is_file():
        print('Verified cleanup is already recorded; no further deletion performed.')
        return
    rows = json.loads((final / 'copy_verification.json').read_text(encoding='utf-8'))
    candidates = {}
    for row in rows:
        source = Path(row['source'])
        if source.is_relative_to(final):
            source = outputs / 'final_pre031_verified_hold' / source.relative_to(final)
        candidates.setdefault(source, []).append(row)
    removed, preserved = [], []
    parents = set()
    for source, copies in candidates.items():
        if not fs(source).is_file():
            valid = [r for r in copies if fs(Path(r['destination'])).is_file() and
                     sha(Path(r['destination'])) == r['sha256_before_path_relocation']]
            if valid:
                removed.append({'path': str(source), 'sha256': valid[0]['sha256_before_path_relocation'],
                    'preserved_duplicate': valid[0]['destination'], 'reason': 'already removed in verified cleanup phase'})
            parents.add(source.parent)
            continue
        safe(source, outputs)
        digest = sha(source)
        valid = [r for r in copies if r['sha256_before_path_relocation'] == digest and
                 fs(Path(r['destination'])).is_file() and sha(Path(r['destination'])) == digest]
        if not valid:
            raise ValueError('No immutable verified duplicate for ' + str(source))
        fs(source).unlink()
        parents.add(source.parent)
        removed.append({'path': str(source), 'sha256': digest,
                        'preserved_duplicate': valid[0]['destination'], 'reason': 'byte-identical archive verified'})
    versions = {'confirmed_waiting_20261018_v020_r2': '0.2.0',
                'confirmed_waiting_20261018_v030': '0.3.0', 'east_extinguisher_20261018_v031': '0.3.1'}
    for folder, version in versions.items():
        with zipfile.ZipFile(pkg / f'dist/busan_cctv_analysis-{version}-py3-none-any.whl') as z:
            entries = {n: z.read(n) for n in z.namelist() if n.startswith('cctv/') and not n.endswith('/')}
        for name in ('installed', 'installed_final'):
            installed = outputs / folder / name
            if not installed.is_dir(): continue
            assert not (installed / 'pyvenv.cfg').exists()
            for path, expected in entries.items():
                assert (installed / path).read_bytes() == expected, path
            known = {'cctv', 'bin', f'busan_cctv_analysis-{version}.dist-info'}
            assert {p.name for p in installed.iterdir()} <= known
            if (installed / 'bin').exists():
                assert {p.name for p in (installed / 'bin').iterdir()} <= {'cctv-analysis.exe', 'cctv-analysis'}
            safe(installed, outputs)
            shutil.rmtree(fs(installed))
            parents.add(installed.parent)
            removed.append({'path': str(installed), 'reason': 'temporary pip target; package files byte-identical to versioned wheel'})
    # Build/lib is generated only; ensure every packaged source asset matches.
    build = pkg / 'build'
    if build.is_dir():
        for p in (build / 'lib/cctv').rglob('*'):
            if p.is_file(): assert p.read_bytes() == (pkg / 'src/cctv' / p.relative_to(build / 'lib/cctv')).read_bytes()
        assert {p.name for p in build.iterdir()} <= {'lib', 'bdist.win-amd64'}
        safe(build, pkg)
        shutil.rmtree(fs(build))
        removed.append({'path': str(build), 'reason': 'generated build/lib equals current package source'})
    for p in (pkg / 'dist').iterdir():
        if p.name in {f'busan_cctv_analysis-{v}{suffix}' for v in ('0.1.0','0.2.0','0.3.0')
                      for suffix in ('-py3-none-any.whl', '-handoff.zip')}:
            safe(p, pkg / 'dist')
            digest = sha(p); p.unlink()
            removed.append({'path': str(p), 'sha256': digest, 'reason': 'explicitly superseded release; 0.3.1 retained'})
    # Failed staging attempt: every file must match the immutable original archive.
    failed = outputs / 'final_consolidation_staging_031'
    if failed.is_dir():
        for folder, dirs, files in os.walk(failed):
            for name in files:
                p = Path(folder) / name
                counterpart = final / p.relative_to(failed)
                assert sha(p) == sha(counterpart), p
        safe(failed, outputs); shutil.rmtree(fs(failed))
        removed.append({'path': str(failed), 'reason': 'failed path-length copy; every file duplicated in immutable archive'})
    # Remove empty ancestors only; runtime caches and unreviewed files remain.
    for parent in list(parents):
        while parent != outputs and parent.is_relative_to(outputs):
            parents.add(parent); parent = parent.parent
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try: fs(parent).rmdir()
        except (OSError, FileNotFoundError): pass
    for folder in [outputs / n for n in versions] + [outputs / 'confirmed_waiting_20261018_v020', outputs / 'final_pre031_verified_hold']:
        if folder.exists(): preserved.append({'path': str(folder), 'reason': 'remaining runtime cache or unreviewed files; not inspected/deleted'})
    report = {'deleted': removed, 'retained_runtime_directories': preserved,
              'preserved': ['outputs/final: canonical results, immutable old logs/media and common verification',
                            'raw source videos, models, MICC, virtual environments, manual truth/reviews',
                            'source/config/tests/docs, latest 0.3.1 wheel and handoff ZIP'],
              'deleted_count': len(removed)}
    (final / 'cleanup_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'deleted_items': len(removed), 'retained_runtime_roots': len(preserved)}, ensure_ascii=True))


if __name__ == '__main__':
    main()
