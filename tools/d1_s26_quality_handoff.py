"""Export existing CPU references without inference, images, models or device access."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def build(root):
    catalog = root / 'validation_inputs/canonical_png_v2_final/manifest.json'
    subset = root / 'validation_inputs/subset_manifest.json'
    sources = {s['id']: s for s in load(subset)['samples']}
    samples = []
    for item in load(catalog):
        sid = item['sample_id']
        folder = root / 'resume_20260920T090545Z/host_classification_v3' / sid
        golden = load(folder / 'golden.json')
        for path, expected in (
            (catalog.parent / item['filename'], item['sha256']),
            (folder / 'input.f32le', golden['input_tensor_sha256']),
            (folder / 'output_0.f32le', golden['raw_output_sha256']),
        ):
            if digest(path.read_bytes()) != expected:
                raise ValueError('source hash mismatch: ' + sid)
        if golden['image_sha256'] != item['sha256']:
            raise ValueError('reference input mismatch: ' + sid)
        raw = (folder / 'output_0.f32le').read_bytes()
        if len(raw) != 4000:
            raise ValueError('expected float32[1000]')
        values = list(struct.unpack('<1000f', raw))
        if not all(math.isfinite(v) for v in values):
            raise ValueError('non-finite reference')
        if [r['class_index'] for r in golden['results']] != sorted(range(1000), key=lambda i: (-values[i], i))[:5]:
            raise ValueError('top5 mismatch')
        source = sources[sid]
        metadata = source['metadata']
        reference = {k: v for k, v in golden.items() if k != 'command'}
        samples.append(dict(
            image=item, source_url=source['source_url'], selection_class=source['selection_class'],
            attribution={k: metadata[k] for k in ('Author', 'OriginalLandingURL', 'License', 'Title')},
            reference=reference, reference_source_sha256=digest((folder / 'golden.json').read_bytes()),
            output_float32=values))
    if len(samples) != 20 or len({s['image']['sample_id'] for s in samples}) != 20:
        raise ValueError('expected original 20 images')
    return dict(schema='s26-quality-handoff-v1', role='engineering_equivalence_not_imagenet_ground_truth',
                latest_arrival_repeated_sample='00575b9132bb3746',
                source_catalog_sha256=digest(catalog.read_bytes()),
                source_subset_sha256=digest(subset.read_bytes()), samples=samples)


def verify(bundle):
    from tools.d1_probe_compare import finite_comparison
    if len(bundle['samples']) != 20:
        raise ValueError('sample count')
    for sample in bundle['samples']:
        reference = sample['reference']
        values = sample['output_float32']
        if digest(struct.pack('<1000f', *values)) != reference['raw_output_sha256']:
            raise ValueError('JSON float32 round-trip mismatch')
        if not finite_comparison(values, values)['passed']:
            raise ValueError('self comparison failed')
        changed = list(values)
        changed[0] += 1
        if finite_comparison(values, changed)['passed']:
            raise ValueError('mismatch not rejected')
    return dict(samples=20, raw_output_elements=20000, float32_hash_round_trip=True,
                comparator_self_and_mismatch=True, device_commands=0, new_inference=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args()
    if args.source_root:
        if args.bundle.exists():
            raise ValueError('refuse to overwrite existing handoff')
        bundle = build(args.source_root)
        verify(bundle)
        args.bundle.parent.mkdir(parents=True, exist_ok=True)
        args.bundle.write_text(json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(verify(load(args.bundle)), indent=2))


if __name__ == '__main__':
    main()
