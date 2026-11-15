"""A spoken line of a shot that starts in the last two seconds of a render part is said in the next part (night test
2026-10-20: a line of a shot starting 0.3 s before the part's end was spoken from 1.3 s on, over the shot before). Since the
Ref2VA minute (2026-10-20) the part edge moves first, so the shot gets its two seconds (core/boundaries.py); the line moves
only where the edge cannot."""
import json
import unittest

from _pack import module

ctx, project, chunks = module("ng.core.context"), module("ng.core.project"), module("ng.core.chunks")
shot_share, bridge = module("ng.core.shot_share"), module("ng.core.legacy_bridge")
LUNA = ctx.ContextItem("luna", "Luna", "image", "luna.png", usage=("reference",), content=("character",), description="A woman.")


def plan(second_start, text="@Luna stops."):
    line = {"schema_version": 1, "text": "The moon is bright tonight.", "speaker_id": "luna", "voice": "a calm young woman",
            "language": "English", "delivery": "says"}
    shots = [{"id": "a", "start": 0, "end": second_start, "text": "@Luna walks.", "media": [{"schema_version": 1, "context_id": "luna", "role": "context"}]},
             {"id": "b", "start": second_start, "end": 15, "text": text, "spoken": [line],
              "media": [{"schema_version": 1, "context_id": "luna", "role": "context"}]}]
    context = ctx.DirectorContext(shots_text=json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": shots}),
                                  items=(LUNA,), project_seconds=15, width=1280, height=704, music="N/A", soundscape="Quiet.")
    return project.plan_project(context, 0, chunks.ContinuityPlan("video_audio"))


class SpokenPart(unittest.TestCase):
    def test_a_shot_starting_late_in_a_part_moves_the_part_edge_and_speaks_where_it_starts(self):
        result = plan(7)                     # 7.0 s lay 0.3 s before the edge of a 7.29 s first part
        self.assertEqual(len(result.plan.chunks), 2)
        offset = 7 * 24 - result.plan.chunks[0].story_end_f
        self.assertTrue(offset <= -48 or offset >= 60, "the shot starts 2 s before the edge or 2.5 s after it, not at it")
        speaking = 0 if offset < 0 else 1
        self.assertIn("bright tonight", result.compiled[speaking].prompt)
        self.assertNotIn("bright tonight", result.compiled[1 - speaking].prompt)
        self.assertNotIn("has no spoken line", " ".join(i.text for i in result.issues))

    def test_a_line_of_a_shot_starting_late_in_a_part_moves_to_the_next(self):
        late = chunks.ChunkShot(1, 200, 238, "", carried=False, continues=True, shot_start_f=168)
        part = chunks.Chunk(0, 0, 175, 0, shots=(late,))
        nxt = chunks.Chunk(1, 175, 185, 22, shots=(chunks.ChunkShot(1, 0, 207, "", carried=True, continues=False, shot_start_f=168),))
        self.assertFalse(shot_share.lines_here(late, part))      # 7 frames of the shot in this part
        self.assertTrue(shot_share.lines_here(nxt.shots[0], nxt))

    def test_a_line_of_a_shot_with_room_stays_where_it_starts(self):
        result = plan(3)
        self.assertIn("bright tonight", result.compiled[0].prompt)
        self.assertNotIn("bright tonight", result.compiled[1].prompt)

    def test_the_part_without_the_lines_does_not_show_the_shot_speaking(self):
        # 75 s ref2va project (2026-11): the carried tail kept "she speaks in a soft voice" without its <d> line, and H3
        # made up words for it
        result = plan(3, "@Luna stops at the window and speaks in a calm voice.")
        self.assertEqual(len(result.compiled), 2)
        self.assertIn("speaks in a calm voice", result.compiled[0].prompt)
        self.assertNotIn("speaks", result.compiled[1].prompt)
        self.assertIn("stops at the window", result.compiled[1].prompt)

    def test_a_shot_whose_lines_move_to_the_next_part_does_not_speak_before_them(self):
        late = chunks.ChunkShot(1, 200, 238, "@Luna stops and speaks in a calm voice.", carried=False, continues=True,
                                shot_start_f=168, shot_end_f=360,
                                spoken=(chunks.SpokenLine("The moon is bright tonight.", speaker_id="luna"),))
        context = ctx.DirectorContext(items=(LUNA,), shots_text=json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": []}))
        text = bridge._shot_text(late, lambda t: t.replace("@Luna", "@ref1"), context=context, chunk=chunks.Chunk(0, 0, 175, 0, shots=(late,)))
        self.assertNotIn("speaks", text)
        self.assertNotIn("bright tonight", text)
        self.assertIn("@ref1 stops", text)


if __name__ == "__main__":
    unittest.main()
