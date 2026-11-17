"""Which earlier parts a part's render depends on (core/project.ChunkJob.chain_start), the span adapters/resume.py keys a
part over. A part that starts fresh, with no pin and no Place picture, takes nothing from the parts before it, so a change
before it does not render it again (user 2026-11-16, for iterating on parts after a cut)."""
import json
import unittest
from types import SimpleNamespace

from _pack import module

ctx, chunks, project = module("ng.core.context"), module("ng.core.chunks"), module("ng.core.project")


def plan(place=False, continuity="video_audio"):
    records = [{"id": "s%d" % n, "start": 6 * n, "end": 6 * n + 6, "text": "Shot %d." % n, "media": []} for n in range(4)]
    if place:
        records[3]["place_from"] = "s0"
    document = json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": records})
    return project.jobs(project.plan_project(ctx.DirectorContext(shots_text=document, project_seconds=24, mode="ref2va",
                                                                 width=1024, height=576), 6, chunks.ContinuityPlan(continuity)))


class ChainStart(unittest.TestCase):
    def test_pinned_parts_depend_on_every_part_before(self):
        self.assertEqual([job.chain_start for job in plan()], [0, 0, 0, 0])

    def test_a_part_that_starts_fresh_starts_its_own_chain(self):
        heads = (0, 22, 0, 22, 22, 0)                     # cuts at parts 3 and 6, as at "Render part: New part (cut)" shots
        parts = tuple(chunks.Chunk(n, 100 * n, 100, head) for n, head in enumerate(heads))
        compiled = tuple(SimpleNamespace(refs=()) for _ in heads)
        made = project.ProjectPlan(ctx.DirectorContext(), SimpleNamespace(chunks=parts), compiled, ())
        self.assertEqual([job.chain_start for job in project.jobs(made)], [0, 0, 2, 2, 2, 5])

    def test_a_part_with_a_place_picture_depends_on_the_parts_before(self):
        jobs = plan(place=True)
        placed = next(job for job in jobs if any(r.ctx_id.startswith("h3place_") for r in job.compiled.refs))
        self.assertEqual(placed.chunk.head_frames, 0, "a cut back to the place")
        self.assertEqual(placed.chain_start, 0, "its picture comes from an earlier part's render")

    def test_without_continuity_every_part_stands_alone(self):
        self.assertEqual([job.chain_start for job in plan(continuity="none")], list(range(4)))


if __name__ == "__main__":
    unittest.main()
