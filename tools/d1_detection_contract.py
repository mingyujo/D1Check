"""Explicit EfficientDet contract and host equivalence reference, never ground truth.

Optional runtime dependencies are imported only by the CLI. All model/image/output
bytes live outside the repository. Existing model-probe-v1 artifacts are immutable.
"""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import zipfile

MODEL_SHA256 = '40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58'
LABEL_SHA256 = 'f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2'
PREPROCESSING = {'id': 'rgb8-bilinear-q16-stretch-v1', 'size': [320, 320],
                 'channels': 'RGB', 'source': 'lossless RGB8 PNG; EXIF already applied',
                 'sampling': 'half-pixel centers; clamp edges; Q16 floor weights; round half up',
                 'crop': 'none', 'padding': 'none', 'normalization': '(float32(RGB)-127.5)/127.5'}
DECODER = {'id': 'efficientdet-metadata-yxhw-nms-v1', 'score_threshold': 0.5,
           'nms_iou_threshold': 0.3, 'class_offset': 0, 'class_selection': 'argmax per anchor; first index on tie',
           'nms': 'class agnostic greedy; suppress IoU > threshold', 'max_results': -1,
           'order': 'score descending, label, box; anchor index breaks pre-NMS ties',
           'box': 'unclipped original-image float xywh; metadata normalized anchors', 'sigmoid': False}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def resize_rgb(rgb, width, height, size=320):
    """Platform-independent integer bilinear interpolation (no Pillow resize)."""
    if width <= 0 or height <= 0 or len(rgb) != width * height * 3 or size <= 0:
        raise ValueError('invalid RGB geometry')
    def axis(length):
        positions = []
        for i in range(size):
            q = max(0, min((length - 1) * 65536, ((2 * i + 1) * length * 65536) // (2 * size) - 32768))
            a, f = divmod(q, 65536)
            positions.append((a, min(a + 1, length - 1), f))
        return positions
    xs, ys = axis(width), axis(height)
    result = bytearray(size * size * 3)
    for y, (y0, y1, fy) in enumerate(ys):
        for x, (x0, x1, fx) in enumerate(xs):
            for c in range(3):
                a = rgb[(y0 * width + x0) * 3 + c] * (65536 - fx) + rgb[(y0 * width + x1) * 3 + c] * fx
                b = rgb[(y1 * width + x0) * 3 + c] * (65536 - fx) + rgb[(y1 * width + x1) * 3 + c] * fx
                result[(y * size + x) * 3 + c] = (a * (65536 - fy) + b * fy + 2147483648) // 4294967296
    return bytes(result)


def iou(a, b):
    x = max(0., min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0., min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    union = a[2] * a[3] + b[2] * b[3] - x * y
    return x * y / union if union > 0 else 0.


def decode(scores, locations, anchors, labels, width, height):
    if len(scores) != len(locations) or len(scores) != len(anchors) or width <= 0 or height <= 0:
        raise ValueError('decoder geometry mismatch')
    candidates = []
    for index, (row, loc, anchor) in enumerate(zip(scores, locations, anchors)):
        if len(row) != len(labels) or len(loc) != 4 or len(anchor) != 4:
            raise ValueError('decoder tensor mismatch')
        if not all(math.isfinite(float(v)) for v in [*row, *loc, *anchor]):
            raise ValueError('non-finite decoder input')
        cls = max(range(len(row)), key=lambda k: row[k])
        score = float(row[cls])
        if score < DECODER['score_threshold']:
            continue
        dy, dx, dh, dw = map(float, loc)
        ax, ay, aw, ah = map(float, anchor)
        w, h = math.exp(dw) * aw, math.exp(dh) * ah
        cx, cy = dx * aw + ax, dy * ah + ay
        box = [(cx - w / 2) * width, (cy - h / 2) * height, w * width, h * height]
        if not all(math.isfinite(v) for v in box) or w <= 0 or h <= 0:
            raise ValueError('invalid decoded box')
        candidates.append((index, {'label': labels[cls], 'score': score, 'box': box}))
    candidates.sort(key=lambda x: (-x[1]['score'], x[0]))
    accepted = []
    for _, row in candidates:
        if all(iou(row['box'], prior['box']) <= DECODER['nms_iou_threshold'] for prior in accepted):
            accepted.append(row)
    return sorted(accepted, key=lambda x: (-x['score'], x['label'], x['box']))


def model_contract(path):
    from mediapipe.tasks.metadata import schema_py_generated as schema
    from mediapipe.tasks.metadata import metadata_schema_py_generated as metadata
    from mediapipe.tasks.metadata import object_detector_metadata_schema_py_generated as detection
    data = path.read_bytes()
    if sha(data) != MODEL_SHA256:
        raise ValueError('exact model SHA-256 mismatch')
    model = schema.Model.GetRootAs(data, 0)
    md = next(model.Metadata(i) for i in range(model.MetadataLength()) if model.Metadata(i).Name() == b'TFLITE_METADATA')
    meta = metadata.ModelMetadata.GetRootAs(bytes(model.Buffers(md.Buffer()).DataAsNumpy()), 0)
    sub = meta.SubgraphMetadata(0)
    custom = next(sub.CustomMetadata(i) for i in range(sub.CustomMetadataLength())
                  if sub.CustomMetadata(i).Name() == b'DETECTOR_METADATA')
    opts = detection.ObjectDetectorOptions.GetRootAs(bytes(custom.DataAsNumpy()), 0)
    dec = opts.TensorsDecodingOptions()
    if (dec.NumClasses(), dec.NumBoxes(), dec.NumCoords(), dec.XScale(), dec.YScale(), dec.WScale(),
        dec.HScale(), dec.ApplyExponentialOnBoxSize(), dec.SigmoidScore()) != (90, 19206, 4, 1, 1, 1, 1, True, False):
        raise ValueError('unsupported detector metadata')
    fixed = opts.SsdAnchorsOptions().FixedAnchorsSchema()
    anchors = [[a.XCenter(), a.YCenter(), a.Width(), a.Height()]
               for a in (fixed.Anchors(i) for i in range(fixed.AnchorsLength()))]
    with zipfile.ZipFile(path) as archive:
        label_bytes = archive.read('labels.txt')
    if sha(label_bytes) != LABEL_SHA256 or len(anchors) != 19206:
        raise ValueError('label/anchor identity mismatch')
    return anchors, label_bytes.decode().splitlines()


def generate(model, image, output, tensor_path=None):
    import numpy as np
    from PIL import Image
    from ai_edge_litert.interpreter import Interpreter
    anchors, labels = model_contract(model)
    image_bytes = image.read_bytes()
    with Image.open(image) as im:
        if im.format != 'PNG' or im.mode != 'RGB' or im.getexif().get(274, 1) != 1:
            raise ValueError('reference requires lossless RGB PNG with applied orientation')
        width, height = im.size
        rgb = resize_rgb(im.tobytes(), width, height)
    tensor = ((np.frombuffer(rgb, dtype=np.uint8).astype(np.float32) - np.float32(127.5)) / np.float32(127.5)).reshape(1, 320, 320, 3)
    if tensor_path is not None:
        tensor = np.frombuffer(tensor_path.read_bytes(), dtype='<f4').reshape(1, 320, 320, 3).copy()
    if not np.isfinite(tensor).all():
        raise ValueError('non-finite input')
    interpreter = Interpreter(model_path=str(model), num_threads=1)
    interpreter.allocate_tensors()
    inp, outs = interpreter.get_input_details(), interpreter.get_output_details()
    if len(inp) != 1 or len(outs) != 2 or inp[0]['shape'].tolist() != [1, 320, 320, 3] or [t['shape'].tolist() for t in outs] != [[1, 19206, 90], [1, 19206, 4]] or any(t['dtype'] != np.float32 or t['quantization'] != (0.0, 0) for t in [*inp, *outs]):
        raise ValueError('runtime tensor metadata does not match pinned contract')
    interpreter.set_tensor(inp[0]['index'], tensor)
    hashes = []
    for _ in range(3):
        interpreter.invoke()
        raw = [interpreter.get_tensor(t['index']) for t in outs]
        hashes.append([sha(a.astype('<f4').tobytes()) for a in raw])
    if hashes[0] != hashes[1] or hashes[1] != hashes[2]:
        raise ValueError('nondeterministic host reference')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'input.f32le').write_bytes(tensor.astype('<f4').tobytes())
    for i, a in enumerate(raw):
        (output / f'output_{i}.f32le').write_bytes(a.astype('<f4').tobytes())
    def metadata(t):
        return {'index': int(t['index']), 'name': t['name'], 'shape': t['shape'].tolist(),
                'dtype': str(t['dtype']), 'quantization': t['quantization']}
    record = {'status': 'engineering_reference_not_ground_truth', 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'generator_sha256': sha(Path(__file__).read_bytes()), 'model_sha256': sha(model.read_bytes()),
              'image_sha256': sha(image_bytes), 'image_size': [width, height], 'preprocessing': PREPROCESSING,
              'preprocessing_sha256': sha(canonical(PREPROCESSING)), 'input_tensor_sha256': sha(tensor.astype('<f4').tobytes()),
              'input_override': str(tensor_path) if tensor_path else None, 'runtime': 'ai-edge-litert',
              'runtime_version': importlib.metadata.version('ai-edge-litert'), 'cpu_threads': 1,
              'tensor_metadata': {'inputs': list(map(metadata, inp)), 'outputs': list(map(metadata, outs))},
              'raw_output_sha256': hashes[0], 'decoder': DECODER, 'decoder_sha256': sha(canonical(DECODER)),
              'decoded': decode(raw[0][0], raw[1][0], anchors, labels, width, height),
              'command': [sys.executable, *sys.argv], 'quality_evaluated': False}
    (output / 'golden.json').write_bytes(canonical(record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tensor', type=Path, help='Explicit diagnostic same-tensor replay; recorded separately')
    args = parser.parse_args()
    print(json.dumps(generate(args.model, args.image, args.output, args.tensor), indent=2))


if __name__ == '__main__':
    main()
