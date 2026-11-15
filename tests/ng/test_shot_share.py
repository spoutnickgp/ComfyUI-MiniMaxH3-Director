"""A shot over several render parts gives each part its own share of the action (real runs 2026-10-12 repeated it)."""
import json
import unittest

from _pack import module

share = module("ng.core.shot_share")
ctx, chunks, project = module("ng.core.context"), module("ng.core.chunks"), module("ng.core.project")

WALK = ("Aurelia turns around and walks away deep into the dark stone hall until she is small in the distance, then turns back and "
        "walks toward the camera until her face fills the frame in a close-up. At the end she stands still, looks into the camera "
        "with her cyan-blue eyes and smiles confidently.")
BEATS = "A calm bedroom. 0–2.5s: They recline. 2.5–5s: A touch. 5–7.5s: They sit up. 7.5–10s: The magic fades."


class Share(unittest.TestCase):
    def test_a_part_with_the_whole_shot_keeps_the_text(self):
        self.assertEqual(share.share(WALK, 0, 240, 0, 240, 0), WALK)
        self.assertEqual(share.share(WALK, -1, -1, 100, 200, 78), WALK, "no span known: unchanged")

    def test_clauses_follow_the_shot_time(self):
        first, second = share.share(WALK, 0, 481, 0, 240, 0), share.share(WALK, 0, 481, 240, 481, 218)
        self.assertTrue(first.endswith("in the distance, then turns back and walks toward the camera until her face fills the frame "
                                       "in a close-up."), first)
        self.assertNotIn("At the end", first)
        self.assertTrue(second.startswith("then turns back"), second)
        self.assertNotIn("walks away", second)
        self.assertIn("At the end she stands still", second)

    def test_beats_go_to_their_part_retimed(self):
        self.assertEqual(share.share(BEATS, 0, 240, 0, 121, 0), "A calm bedroom. 0–2.5s: They recline. 2.5–5s: A touch.")
        self.assertEqual(share.share(BEATS, 0, 240, 121, 240, 99), "A calm bedroom. 0.9–3.4s: They sit up. 3.4–5.9s: The magic fades.")

    def test_a_shot_only_in_the_pinned_head_gets_no_action(self):
        self.assertEqual(share.share(WALK, 0, 120, 120, 120, 98), share.HEAD_ONLY)

    def test_one_sentence_is_shared_where_its_steps_follow_each_other(self):
        # the control test 2026-10-13: the whole sentence went to both parts and Luna turned away again at 13 s
        text = ("@Luna walks through a dark stone hall with tall gothic arches and candles, away from the camera and back toward it, "
                "ending in a close-up with a calm smile.")
        first, second = share.share(text, 0, 481, 0, 240, 0), share.share(text, 0, 481, 240, 481, 218)
        self.assertIn("away from the camera", first)
        self.assertNotIn("ending in a close-up", first)
        self.assertNotIn("walks through", second)
        self.assertTrue(second.startswith("and back toward it"), second)
        self.assertIn("ending in a close-up", second)

    def test_a_comma_without_a_step_word_does_not_cut(self):
        text = "She wears a glossy black, purple and gold armour and walks slowly through the misty hall toward the stained-glass window."
        self.assertEqual(share.share(text, 0, 481, 240, 481, 218), text)

    def test_tidy_beats_keeps_the_move_when_a_beat_also_says_static(self):
        # qwen3.5:9b, Make H3 prompt 2026-10-18
        text = ("0–5s: @Micha holds her ground. The camera continues its slow push-in. The camera holds a static shot within "
                "this beat. 5–10s: She smiles. The camera holds a static shot.")
        self.assertEqual(share.tidy_beats(text), "0–5s: @Micha holds her ground. The camera continues its slow push-in. "
                                                 "5–10s: She smiles. The camera holds a static shot.")

    def test_tidy_beats_drops_the_marks_of_beats_that_repeat_each_other(self):
        # qwen3.5:9b, AI: split into shots 2026-10-18: the same sentence in both beats
        beat = "A medium shot of @Micha in a steampunk workshop. The camera holds a static shot."
        self.assertEqual(share.tidy_beats("0–5s: %s 5–10s: %s" % (beat, beat)), beat)

    def test_tidy_beats_keeps_only_the_camera_of_a_beat_that_copies_the_action(self):
        # qwen3.5:9b, 2026-10-18: the same description in both beats, only the camera sentence differed
        action = "A full-body shot of @Micha in a steampunk workshop. She looks determined."
        text = "0–5s: %s The camera pushes in with small amplitude at slow speed. 5–10s: %s The camera holds a static shot." % (
            action, action)
        self.assertEqual(share.tidy_beats(text), "0–5s: %s The camera pushes in with small amplitude at slow speed. "
                                                 "5–10s: The camera holds a static shot." % action)

    def test_tidy_beats_leaves_good_beats_and_plain_text(self):
        self.assertEqual(share.tidy_beats(BEATS), BEATS)
        self.assertEqual(share.tidy_beats(WALK), WALK)

    def test_one_sentence_stays_whole(self):
        self.assertEqual(share.share("She dances.", 0, 481, 240, 481, 218), "She dances.")


class WithoutSpeech(unittest.TestCase):
    """A part that does not say a shot's lines drops the shot's speaking actions and keeps the rest of the action."""
    DIALOGUE = module("minimax_plan").DIALOGUE_RE

    def strip(self, text):
        return module("ng.core.shot_speech").without_speech(text, self.DIALOGUE)

    def test_a_speaking_clause_goes_and_the_rest_of_the_sentence_stays(self):
        self.assertEqual(self.strip("@Joss pats the hull with his broad hand and speaks in a slow, gravelly voice, while @Kira's "
                                    "lips stay closed."), "@Joss pats the hull with his broad hand, while @Kira's lips stay closed.")
        self.assertEqual(self.strip("@Kira looks back and answers in a low, clipped voice, then turns to climb."),
                         "@Kira looks back, then turns to climb.")

    def test_the_speaker_keeps_the_next_step(self):
        self.assertEqual(self.strip("@Kira answers in a low voice, then turns to climb."), "@Kira turns to climb.")
        self.assertEqual(self.strip("@Joss sits and she asks in a calm voice, then pours the tea."), "@Joss sits and she pours the tea.")
        self.assertEqual(self.strip("Speaking softly, she smiles."), "She smiles.")

    def test_a_sentence_of_speech_only_goes(self):
        self.assertEqual(self.strip("She speaks in a soft voice. She smiles."), "She smiles.")
        self.assertEqual(self.strip("@Kira nods while @Joss goes on explaining."), "@Kira nods.")
        self.assertEqual(self.strip("She goes on in a soft and warm voice, and sets the cup down."), "She sets the cup down.")
        self.assertEqual(self.strip("A loud man's voice shouts from behind the door."), "")
        # panels 11 and 12 of the 75 s project
        self.assertEqual(self.strip("@Girl tilts her head up and starts to speak in a soft, hesitant voice, while @Woman's lips stay "
                                    "closed."), "@Girl tilts her head up, while @Woman's lips stay closed.")
        self.assertEqual(self.strip("Someone knocks at the door loudly from outside, and a loud, authoritative man's voice shouts "
                                    "from behind it while the door stays shut."),
                         "Someone knocks at the door loudly from outside while the door stays shut.")

    def test_every_delivery_verb_counts(self):
        for verb in ("speaks", "says something", "answers", "asks", "shouts", "whispers", "murmurs", "replies", "explains",
                     "goes on", "keeps talking", "continues to speak", "calls out"):
            self.assertEqual(self.strip("She sits. She %s." % verb), "She sits.", verb)

    def test_a_beat_left_empty_goes_with_its_mark(self):
        self.assertEqual(self.strip("0–2s: She sits. 2–4s: She asks in a low voice. 4–6s: She stands."), "0–2s: She sits. 4–6s: She stands.")

    def test_what_is_not_speech_stays(self):
        for text in ("He goes on walking toward the door.", "Her whispers fade into the hum of the fridge.",
                     "An off-screen voiceover is heard, and @Kira's lips stay closed.", "She sings to the moon.",
                     "@Joss and @Kira sit at the table."):
            self.assertEqual(self.strip(text), text)
        self.assertEqual(self.strip("@ref1 [English] says: Hello there."), "@ref1 [English] says: Hello there.", "a spoken line")

    def test_only_a_shot_whose_lines_are_dropped_loses_its_speaking(self):
        speech = module("ng.core.shot_speech")
        self.assertEqual(speech.without_lines("She sits and speaks.\n@ref1 [English] says: Hello.", self.DIALOGUE), "She sits.")
        self.assertEqual(speech.without_lines("She sits and speaks.", self.DIALOGUE), "She sits and speaks.",
                         "no line in the shot: the user's own words stay")


class Compiled(unittest.TestCase):
    def plan(self, records, seconds, part_seconds, mode="ref2va", whole=False):
        document = json.dumps({"format": "h3-director-shots", "schema_version": 1, "shots": records})
        items = (ctx.ContextItem("hero", "Hero", "image", "hero.png", usage=("reference",)),)
        result = project.plan_project(ctx.DirectorContext(shots_text=document, items=items, project_seconds=seconds, mode=mode),
                                      part_seconds, chunks.ContinuityPlan("video_audio"))
        return result if whole else result.compiled

    def test_a_long_shot_is_not_played_again_in_its_second_part(self):
        compiled = self.plan([{"id": "s", "start": 0, "end": 20, "text": WALK.replace("Aurelia", "@Hero"), "media": []}], 20, 10)
        self.assertEqual(len(compiled), 2)
        self.assertNotIn("At the end", compiled[0].prompt)
        self.assertNotIn("walks away", compiled[1].prompt)
        self.assertIn("Continue the same scene and action from the preceding video", compiled[1].prompt)

    def test_a_shot_that_lives_only_in_the_head_is_not_replayed(self):
        # 6 shots of 5 s in 10 s parts: the head of part 2 still holds the end of shot 2 (the user's 30 s storyboard).
        records = [{"id": "p%d" % n, "start": 5 * (n - 1), "end": 5 * n, "text": "Action number %d happens." % n, "media": []}
                   for n in range(1, 7)]
        result = self.plan(records, 30, 10, whole=True)
        for chunk, part in list(zip(result.plan.chunks, result.compiled))[1:]:
            replayed = [n for n in range(1, 7) if "Action number %d happens." % n in part.prompt]
            self.assertTrue(all(n * 120 > chunk.story_start_f for n in replayed), (part.index, replayed))
        # since 2026-10-20 a part edge moves off a shot start (core/boundaries.py: shot 3 began 0.04 s before the edge at
        # 10.12 s), so in this storyboard no shot lives in a head only any more
        self.assertEqual(share.share("Action. More.", 0, 120, 130, 130, 108), share.HEAD_ONLY)


if __name__ == "__main__":
    unittest.main()
