"""Per-shot LoRAs: read from the shot document, carried into the render parts, switched on per part."""
import json
import unittest

from _pack import module

chunks = module("ng.core.chunks")
shots = module("ng.core.shots")
shot_document = module("ng.core.shot_document")
shot_loras = module("ng.core.shot_loras")
issues = module("ng.core.issues")

VIDEO = chunks.ContinuityPlan("video_audio", 22, 24)


def document(*records):
    return json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": list(records)})


def shot(identity, start, end, loras=None):
    record = {"id": identity, "start": start, "end": end, "text": identity}
    if loras is not None:
        # entries as the Studio writes them; a list of something else is passed on unchanged to test the refusal
        record["loras"] = [{"schema_version": 1, **l} for l in loras] if isinstance(loras, list) else loras
    return record


def plan(text, seconds, chunk_seconds):
    parsed, _ = shots.parse_shots(text, seconds * 24)
    return chunks.plan_chunks(seconds * 24, chunk_seconds * 24, VIDEO, parsed)


def names(chunk):
    return [(lora.name, lora.strength) for lora in shot_loras.chunk_loras(chunk)]


class Document(unittest.TestCase):
    def test_a_shot_reads_its_loras_with_strength_defaulting_to_one(self):
        parsed, _ = shots.parse_shots(document(shot("a", 0, 5, [{"name": "ink.safetensors"}, {"name": "x/y.safetensors", "strength": 0.6}])), 120)
        self.assertEqual([(l.name, l.strength) for l in parsed[0].loras], [("ink.safetensors", 1.0), ("x/y.safetensors", 0.6)])

    def test_an_entry_without_its_version_is_refused(self):
        record = {"id": "a", "start": 0, "end": 5, "text": "a", "loras": [{"name": "ink.safetensors"}]}
        with self.assertRaises(issues.SchemaError):
            shots.parse_shots(document(record), 120)

    def test_a_shot_without_loras_has_none(self):
        parsed, _ = shots.parse_shots(document(shot("a", 0, 5)), 120)
        self.assertEqual(parsed[0].loras, ())

    def test_bad_entries_are_refused_not_dropped(self):
        for bad in ([{"name": ""}], [{"strength": 1}], [{"name": "a", "strength": 11}], [{"name": "a", "strength": "1"}], "ink"):
            with self.assertRaises(issues.SchemaError, msg=bad):
                shots.parse_shots(document(shot("a", 0, 5, bad)), 120)


class PerPart(unittest.TestCase):
    def test_each_part_carries_the_loras_of_the_shots_it_samples(self):
        text = document(shot("a", 0, 10, [{"name": "a.safetensors"}]), shot("b", 10, 20), shot("c", 20, 30, [{"name": "c.safetensors", "strength": 0.5}]))
        parts = plan(text, 30, 10).chunks
        self.assertEqual(len(parts), 3)
        for part in parts:
            sampled = {s.shot_id for s in part.shots if s.local_end_f > part.head_frames}
            expected = [n for n, sid in (("a.safetensors", "a"), ("c.safetensors", "c")) if sid in sampled]
            self.assertEqual([n for n, _ in names(part)], expected, part.index)
        self.assertIn(("a.safetensors", 1.0), names(parts[0]))
        self.assertIn(("c.safetensors", 0.5), names(parts[-1]))

    def test_a_shot_only_in_the_pinned_head_does_not_switch_its_lora_on(self):
        part = chunks.Chunk(index=1, story_start_f=240, delivered_frames=221, head_frames=22, shots=(
            chunks.ChunkShot(0, 0, 22, "a", carried=True, continues=False, shot_id="a", loras=(shot_document.ShotLora("a.safetensors"),)),
            chunks.ChunkShot(1, 22, 243, "b", carried=False, continues=False, shot_id="b", loras=(shot_document.ShotLora("b.safetensors"),))))
        self.assertEqual(names(part), [("b.safetensors", 1.0)])

    def test_a_lora_on_several_shots_of_one_part_is_used_once_at_its_strongest(self):
        text = document(shot("a", 0, 3, [{"name": "s.safetensors", "strength": 0.4}]), shot("b", 3, 6, [{"name": "s.safetensors", "strength": -0.9}]))
        part = plan(text, 6, 10).chunks[0]
        self.assertEqual(names(part), [("s.safetensors", -0.9)])

    def test_pictures_carry_their_shots_loras(self):
        stills = module("ng.core.stills")
        piece = stills._chunk(0, shots.Shot(1, 0, 120, "a", id="a", loras=(shot_document.ShotLora("a.safetensors", 0.7),)), True)
        self.assertEqual(names(piece), [("a.safetensors", 0.7)])


class Persistence(unittest.TestCase):
    def test_loras_survive_a_chunk_round_trip(self):
        part = plan(document(shot("a", 0, 5, [{"name": "a.safetensors", "strength": 0.3}])), 5, 10).chunks[0]
        again = chunks.Chunk.from_dict(json.loads(json.dumps(part.to_dict())))
        self.assertEqual(names(again), [("a.safetensors", 0.3)])

    def test_a_shot_without_loras_keeps_its_old_dict_so_resumed_parts_stay_valid(self):
        part = plan(document(shot("a", 0, 5)), 5, 10).chunks[0]
        self.assertNotIn("loras", part.shots[0].to_dict())


if __name__ == "__main__":
    unittest.main()
