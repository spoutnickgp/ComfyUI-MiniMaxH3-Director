"""A shot the user sets to start a new render part (Studio "Render part: New part (cut)", field `part_start` "cut"): the
part opens at the shot with no pin, so the shot before does not run on into it (user 2026-11-16: control over where the
parts join, rather than more automation). The edge goes through the same code as "Place like Shot N" (core/project.py)."""
import json
import unittest

from _pack import module

ctx, project, chunks, frames = module("ng.core.context"), module("ng.core.project"), module("ng.core.chunks"), module("ng.core.frames")
LUNA = ctx.ContextItem("luna", "Luna", "image", "luna.png", usage=("reference",), content=("character",), description="A woman.")
TEXTS = ("@Luna walks along a river.", "@Luna sits in a cafe.", "@Luna reads a letter.")


def plan(seconds=(6, 6, 6), marks=None, mode="video_audio", value="cut"):
    starts = [sum(seconds[:n]) for n in range(len(seconds))]
    records = [{"id": "s%d" % (n + 1), "start": start, "end": start + length, "text": TEXTS[n % 3],
                "media": [{"schema_version": 1, "context_id": "luna", "role": "context"}]}
               for n, (start, length) in enumerate(zip(starts, seconds))]
    for shot_id in marks or ():
        next(r for r in records if r["id"] == shot_id)["part_start"] = value
    context = ctx.DirectorContext(shots_text=json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": records}),
                                  items=(LUNA,), project_seconds=sum(seconds), mode="ref2va", music="N/A", soundscape="Quiet.",
                                  width=1024, height=576)
    return project.plan_project(context, 8, chunks.ContinuityPlan(mode, 22))


def start_of(result, shot_id):
    return frames.seconds_to_frames(next(r for r in json.loads(result.context.shots_text)["shots"] if r["id"] == shot_id)["start"])


def codes(result):
    return [issue.code for issue in result.issues]


class PartStart(unittest.TestCase):
    def test_a_marked_shot_opens_an_unpinned_part_at_its_start(self):
        result = plan(marks=["s2"])
        start = start_of(result, "s2")
        self.assertLessEqual(abs(start - 6 * 24), 8, "the shot start moves at most half a grid step")
        part = next(c for c in result.plan.chunks if c.story_start_f == start)
        self.assertGreater(part.index, 0)
        self.assertEqual(part.head_frames, 0, "a cut: no frames of the shot before")
        self.assertFalse(part.shots[0].carried)
        self.assertEqual(part.shots[0].shot_id, "s2")
        before = result.plan.chunks[part.index - 1]
        self.assertNotIn("s2", [s.shot_id for s in before.shots], "the part before ends where the shot starts")

    def test_a_moved_shot_start_is_reported(self):
        result = plan(marks=["s2"])
        moved = start_of(result, "s2") != 6 * 24
        self.assertEqual("part_start_moved" in codes(result), moved)

    def test_a_mark_too_close_to_the_previous_part_is_not_used(self):
        result = plan(seconds=(2, 8, 8), marks=["s2"])
        self.assertIn("part_start_too_close", codes(result))
        self.assertEqual([c.to_dict() for c in result.plan.chunks], [c.to_dict() for c in plan(seconds=(2, 8, 8)).plan.chunks])

    def test_the_first_shot_and_other_values_change_nothing(self):
        unmarked = [c.to_dict() for c in plan().plan.chunks]
        self.assertEqual([c.to_dict() for c in plan(marks=["s1"]).plan.chunks], unmarked)
        self.assertEqual([c.to_dict() for c in plan(marks=["s2"], value="auto").plan.chunks], unmarked)
        self.assertNotIn("part_start_moved", codes(plan(marks=["s1"])))

    def test_with_a_video_only_pin_the_mark_places_the_edge_too(self):
        result = plan(marks=["s3"], mode="video")
        start = start_of(result, "s3")
        self.assertTrue(any(c.story_start_f == start and c.shots[0].shot_id == "s3" and not c.shots[0].carried
                            for c in result.plan.chunks))

    def test_two_marks_give_parts_that_hold_whole_shots(self):
        result = plan(marks=["s2", "s3"])
        for chunk in result.plan.chunks:
            self.assertEqual(len({s.shot_id for s in chunk.shots}), 1, "each part shows one shot")


if __name__ == "__main__":
    unittest.main()
