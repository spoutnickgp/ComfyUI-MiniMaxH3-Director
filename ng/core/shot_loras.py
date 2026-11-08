"""Per-shot LoRAs: which ones a render part switches on.

A LoRA changes the model's weights, and a render part samples all its frames in one run, so a LoRA is on for a whole part.
The rule is the simplest one: a part carries the LoRAs of every shot it samples new frames of. A shot that only lies in the
part's pinned head is left out; those frames are held from the previous part, not sampled again.
Plain data, no torch, so it can be tested without a GPU."""
from .shot_document import ShotLora


def chunk_loras(chunk):
    """The ShotLoras of `chunk`, in shot order. A LoRA on several of its shots is used once, at its strongest strength."""
    chosen = {}
    for shot in chunk.shots:
        if shot.local_end_f <= chunk.head_frames:
            continue
        for lora in shot.loras:
            known = chosen.get(lora.name)
            if known is None or abs(lora.strength) > abs(known):
                chosen[lora.name] = lora.strength
    return tuple(ShotLora(name, strength) for name, strength in chosen.items())
