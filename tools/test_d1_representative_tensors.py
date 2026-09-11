import hashlib
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("d1_representative_tensors.py")
SPEC = importlib.util.spec_from_file_location("d1_representative_tensors", MODULE_PATH)
assert SPEC and SPEC.loader
TENSORS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TENSORS)


class RepresentativeTensorSetTest(unittest.TestCase):
    CANONICAL_HASH = "ad6f76b120f8ccf0f64a260ee388f7af2b002dc722436f8b19552dcb6f702260"

    def make_dataset(self, root: Path, images_per_class: int = 2) -> tuple[Path, Path]:
        from PIL import Image

        split = root / "val"
        for class_index, wnid in enumerate(TENSORS.IMAGENETTE_WNIDS):
            directory = split / wnid
            directory.mkdir(parents=True)
            for image_index in range(images_per_class):
                image = Image.new(
                    "RGB", (8 + image_index, 9 + image_index),
                    (class_index * 17, image_index * 61, 255 - class_index * 13),
                )
                image.save(directory / f"sample-{image_index}.png")
        wnids = [f"n{index:08d}" for index in range(1000)]
        for index, wnid in enumerate(TENSORS.IMAGENETTE_WNIDS):
            wnids[index * 37] = wnid
        label_map = root / "tf-slim-wnids.txt"
        label_map.write_text("\n".join(wnids) + "\n", encoding="utf-8")
        return root, label_map

    def build(self, root: Path, name: str, seed: int = 7) -> dict:
        dataset, labels = self.make_dataset(root / name)
        return TENSORS.build_tensor_set(
            dataset, root / f"{name}.d1tset", labels, 10, seed,
            "imagenette-test", "https://example.invalid/imagenette", "test fixture",
        )

    def test_container_reproducibility_and_seed_change(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = self.build(root, "a", 7)
            second = self.build(root, "b", 7)
            changed = self.build(root, "c", 8)
            self.assertEqual(first["tensor_set_sha256"], second["tensor_set_sha256"])
            self.assertNotEqual(first["tensor_set_sha256"], changed["tensor_set_sha256"])

    def test_background_offset_and_stratified_selection(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.build(Path(raw), "dataset")
            header = result["header"]
            self.assertEqual(0, header["label_mapping"]["background_index"])
            self.assertEqual(
                [index * 37 + 1 for index in range(10)],
                [sample["mapped_output_index"] for sample in header["samples"]],
            )
            self.assertEqual(
                list(TENSORS.IMAGENETTE_WNIDS),
                [sample["ground_truth_wnid"] for sample in header["samples"]],
            )

    def test_corrupt_and_truncated_container_fail(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            result = self.build(root, "dataset")
            original = Path(result["path"]).read_bytes()
            corrupt = root / "corrupt.d1tset"
            corrupt.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            truncated = root / "truncated.d1tset"
            truncated.write_bytes(original[:100])
            with self.assertRaisesRegex(TENSORS.TensorSetError, "SHA-256"):
                TENSORS.validate_tensor_set(corrupt)
            with self.assertRaises(TENSORS.TensorSetError):
                TENSORS.validate_tensor_set(truncated)

    def test_preprocessing_golden_fixture(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "golden.png"
            image = Image.new("RGB", (8, 8))
            image.putdata([
                ((x * 31 + y * 7) % 256, (x * 13 + y * 29) % 256, (x * y * 17) % 256)
                for y in range(8) for x in range(8)
            ])
            image.save(path)
            tensor = TENSORS.preprocess_image(path)
            golden = json.loads(
                Path(__file__).with_name("fixtures")
                .joinpath("mobilenet_preprocessing_golden_v1.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(224 * 224 * 3 * 4, len(tensor))
            self.assertEqual(
                golden["output_sha256"],
                hashlib.sha256(tensor).hexdigest(),
            )
            first = struct.unpack_from("<f", tensor, 0)[0]
            self.assertGreaterEqual(first, -1.0)
            self.assertLessEqual(first, 1.0)

    def test_preprocessing_canonical_bytes_and_hash_golden(self):
        fixture = (
            Path(__file__).with_name("fixtures") /
            "mobilenet_preprocessing_configuration_v1.canonical.json"
        ).read_bytes().rstrip(b"\n")
        configuration = TENSORS.preprocessing_configuration("12.0.0")
        canonical = TENSORS.preprocessing_canonical_bytes(configuration)
        self.assertEqual(fixture, canonical)
        self.assertEqual(self.CANONICAL_HASH, hashlib.sha256(canonical).hexdigest())

    def rewrite_header(self, source: Path, destination: Path, mutate) -> None:
        content = source.read_bytes()
        header_size = struct.unpack_from("<I", content, 8)[0]
        header = json.loads(content[12:12 + header_size])
        mutate(header)
        encoded = TENSORS.canonical_json_bytes(header)
        destination.write_bytes(
            TENSORS.MAGIC + struct.pack("<I", len(encoded)) + encoded +
            content[12 + header_size:]
        )

    def test_v1_container_and_preprocessing_tampering(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            result = self.build(root, "dataset")
            source = Path(result["path"])
            self.assertEqual(
                result["container_sha256"],
                TENSORS.validate_tensor_set(
                    source, result["container_sha256"]
                )["container_sha256"],
            )
            changed_value = root / "changed-value.d1tset"
            self.rewrite_header(
                source, changed_value,
                lambda header: header["preprocessing"].update(
                    central_crop_fraction=0.9
                ),
            )
            with self.assertRaisesRegex(
                TENSORS.TensorSetError, "declared=.*expected=not_provided.*recomputed="
            ):
                TENSORS.validate_tensor_set(changed_value)
            changed_declared = root / "changed-declared.d1tset"
            self.rewrite_header(
                source, changed_declared,
                lambda header: header["preprocessing"].update(
                    configuration_sha256="0" * 64
                ),
            )
            with self.assertRaisesRegex(TENSORS.TensorSetError, "declared=0{64}"):
                TENSORS.validate_tensor_set(changed_declared)
            with self.assertRaisesRegex(
                TENSORS.TensorSetError, "expected=0{64}.*recomputed="
            ):
                TENSORS.validate_tensor_set(source, "0" * 64)

    def test_validate_mode_does_not_require_build_arguments(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.build(Path(raw), "dataset")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, TENSORS.main(["--validate", result["path"]]))


if __name__ == "__main__":
    unittest.main()
