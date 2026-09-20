"""Hash-bound classification reference, for backend equivalence, not ground truth."""
import argparse
import datetime
import importlib.metadata
import io
import json
from pathlib import Path
import re
import sys
import zipfile

from tools.d1_detection_contract import canonical, require_canonical_png, resize_rgb, sha

MODEL_SHA256 = '6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0'
LABEL_SHA256 = 'e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f'
PREPROCESSING = dict(id='canonical-srgb-q16-stretch-v2', input_contract='canonical-srgb-png-v2',
                     size=224, mean=127, std=128, crop=False, padding=False)


def checked_input(image, expected_sha256):
    if not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
        raise ValueError('expected input SHA-256 required')
    data = Path(image).read_bytes()
    if sha(data) != expected_sha256:
        raise ValueError('actual input bytes do not match declared SHA-256')
    require_canonical_png(data)
    return data


def generate(model, image, expected_sha256, output):
    import numpy as np
    from PIL import Image
    from ai_edge_litert.interpreter import Interpreter
    data = checked_input(image, expected_sha256)
    model_bytes = Path(model).read_bytes()
    if sha(model_bytes) != MODEL_SHA256:
        raise ValueError('model SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(model_bytes)) as archive:
        label_bytes = archive.read('labels_without_background.txt')
    labels = label_bytes.decode().splitlines()
    if sha(label_bytes) != LABEL_SHA256 or len(labels) != 1000:
        raise ValueError('label mapping mismatch')
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'PNG' or im.mode != 'RGB' or im.getexif().get(274, 1) != 1:
            raise ValueError('canonical RGB PNG required')
        width, height = im.size
        rgb = resize_rgb(im.tobytes(), width, height, 224)
    tensor = ((np.frombuffer(rgb, dtype=np.uint8).astype(np.float32)-np.float32(127))/np.float32(128)).reshape(1, 224, 224, 3)
    interpreter = Interpreter(model_content=model_bytes, num_threads=1)
    interpreter.allocate_tensors()
    inp, outs = interpreter.get_input_details(), interpreter.get_output_details()
    if len(inp) != 1 or len(outs) != 1 or inp[0]['shape'].tolist() != [1, 224, 224, 3] or outs[0]['shape'].tolist() != [1, 1000] or any(t['dtype'] != np.float32 or t['quantization'] != (0., 0) for t in inp+outs):
        raise ValueError('unexpected tensor contract')
    interpreter.set_tensor(inp[0]['index'], tensor)
    hashes = []
    for _ in range(3):
        interpreter.invoke()
        raw = interpreter.get_tensor(outs[0]['index'])[0]
        if not np.isfinite(raw).all():
            raise ValueError('non-finite raw output')
        hashes.append(sha(raw.astype('<f4').tobytes()))
    if len(set(hashes)) != 1:
        raise ValueError('nondeterministic host reference')
    results = [dict(label=labels[i], class_index=i, score=float(raw[i]))
               for i in sorted(range(1000), key=lambda i: (-float(raw[i]), i))[:5]]
    metadata = lambda t: dict(index=int(t['index']), name=t['name'], shape=t['shape'].tolist(),
                              dtype=str(t['dtype']), quantization=t['quantization'])
    record = dict(status='engineering_reference_not_ground_truth',
                  generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  generator_sha256=sha(Path(__file__).read_bytes()),
                  resize_module_sha256=sha(Path(resize_rgb.__code__.co_filename).read_bytes()),
                  model_sha256=sha(model_bytes), image_sha256=sha(data), image_size=[width, height],
                  label_sha256=sha(label_bytes), preprocessing=PREPROCESSING,
                  preprocessing_sha256=sha(canonical(PREPROCESSING)),
                  input_tensor_sha256=sha(tensor.astype('<f4').tobytes()), raw_output_sha256=hashes[0],
                  runtime='ai-edge-litert', runtime_version=importlib.metadata.version('ai-edge-litert'),
                  cpu_threads=1, tensor_metadata=dict(inputs=list(map(metadata, inp)), outputs=list(map(metadata, outs))),
                  decoder=dict(top_k=5, class_index_offset=0, ordering='score descending then class index ascending'),
                  results=results, deterministic_invocations=3, command=[sys.executable, *sys.argv])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'input.f32le').write_bytes(tensor.astype('<f4').tobytes())
    (output/'output_0.f32le').write_bytes(raw.astype('<f4').tobytes())
    (output/'golden.json').write_bytes(canonical(record))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--expected-image-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.model, args.image, args.expected_image_sha256, args.output), indent=2))
