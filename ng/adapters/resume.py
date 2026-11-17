"""Pick up a render after a crash: every finished render part's raw latent is kept on disk and reused when the same plan is
queued again, so a run that died after hours only samples the parts it had not finished.

A part's key covers what it was made from: its own plan (chunk, prompt, references and the files behind them), the render
settings, and the parts before it back to the last one that starts fresh (ChunkJob.chain_start), because a continued part
is pinned to the one before. Changing part 5 renders part 5 and the parts after it again, up to the next part with no
pin and no Place picture; parts 1 to 4 come from disk. The models themselves are not in the key: after
swapping a checkpoint, delete the folder. The folder is under ComfyUI's output folder, because ComfyUI empties its temp
folder at every start, which is exactly when a resume is needed.

"Part N only" (render_part) renders one part alone. A continued part takes its head from here (head_source): the previous
part under the current plan, or else that part as an earlier run rendered it from the same plan of its own, found through a
small link file named after that own plan; or no head. Only a part with its real head is kept under its key, so a quick
look never becomes part of the final video."""
import hashlib
import json
import os
import time

import torch
import folder_paths
from comfy.nested_tensor import NestedTensor

from ..core.project import jobs
from ..core.turbo_profiles import part_settings
from ..core import control_timing
from ..core.places import is_place
from .continuation_latent import uses_sound_prefix
from .paths import input_path

FOLDER = "h3-director-resume"
KEEP_DAYS = 14


def folder():
    return os.path.join(folder_paths.get_output_directory(), FOLDER)


def _file(source):
    path = input_path(source) if source else None
    if not path or not os.path.isfile(path):
        return None
    stat = os.stat(path)
    return [stat.st_size, stat.st_mtime_ns]


def _place(job, context_id):
    place = next(p for p in job.project.places if p.context_id == context_id)
    return ["rendered", place.kind, place.view]


def _own(job, settings):
    compiled, chunk, context = job.compiled, job.chunk, job.project.context
    own = {"chunk": chunk.to_dict(), "mode": compiled.mode, "prompt": compiled.prompt, "size": [context.width, context.height],
            "continuity": job.project.plan.continuity.mode,
            # a Place picture is written anew by every render (adapters/places.py); the earlier part it comes from is in the chain
            "refs": [[r.kind, r.ctx_id, r.source, r.start_f, r.length_f, r.trim_start_f,
                      _place(job, r.ctx_id) if is_place(r.ctx_id) else _file(r.source)] for r in compiled.refs]}
    if uses_sound_prefix(job):
        own["continuation_audio"] = "held_prefix_no_guide_v1"
    controls = []
    for clip, a, b, source in control_timing.spans(job) if settings.get("control_strength", 1.0) else ():
        item = context.item(clip.context_id)
        controls.append([item.source, _file(item.source), item.options.control_kind, item.options.end_s, item.length_s, a, b, source])
        if item.options.control_kind == "mask":
            controls[-1].extend([item.options.control_mask, _file(item.options.control_mask), item.options.mask_shape, item.options.mask_grow])
    if controls:
        own["control"] = controls
        own["control_settings"] = [settings.get("control_strength", 1.0), settings.get("control_start", 0.0), settings.get("control_end", 1.0)]
    return own


def part_key(job, settings):
    """Hex key of this part, chained over the parts it depends on (ChunkJob.chain_start)."""
    base = {k: v for k, v in settings.items() if not k.startswith("control_")}
    key = hashlib.sha256(json.dumps(base, sort_keys=True, default=str).encode()).hexdigest()
    for earlier in jobs(job.project)[job.chain_start:job.index + 1]:
        key = hashlib.sha256((key + json.dumps(_own(earlier, settings), sort_keys=True, default=str)).encode()).hexdigest()
    return key[:32]


def _path(key):
    return os.path.join(folder(), key + ".pt")


def _link_path(job, settings):
    """The link file of the part's own plan (no earlier parts in it), which names the key it was last kept under."""
    base = {k: v for k, v in settings.items() if not k.startswith("control_")}
    own = hashlib.sha256(json.dumps([base, _own(job, settings)], sort_keys=True, default=str).encode()).hexdigest()
    return os.path.join(folder(), own[:32] + ".link")


def link(job, settings, key):
    with open(_link_path(job, settings), "w", encoding="utf8") as handle:
        handle.write(key)


def _linked(job, settings):
    try:
        with open(_link_path(job, settings), encoding="utf8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def head_source(job, settings):
    """What a part rendered alone takes from the parts before it: ("own", None) for nothing; ("real", key) the previous
    part under the current plan; ("earlier", key) that part from an earlier run of the same plan of its own; ("none",
    None) nothing kept. A Place picture is from an earlier render too, so it makes any part "earlier"; one that is not
    there stops the render."""
    placed = [ref for ref in job.compiled.refs if is_place(ref.ctx_id)]
    if any(_file(ref.source) is None for ref in placed):
        raise ValueError("Part %d only: it uses a Place picture, which the render of an earlier part makes and which this "
                         "plan does not have yet. Render all parts once, or set the shot to its own place while you try "
                         "this part." % (job.index + 1))
    if not job.chunk.head_frames or job.chunk.continuation_id:
        return ("earlier" if placed else "own"), None
    before = jobs(job.project)[job.index - 1]
    wanted = part_settings(before.compiled.mode, settings)
    key = part_key(before, wanted)
    if has(key):
        return ("earlier" if placed else "real"), key
    linked = _linked(before, wanted)
    return ("earlier", linked) if linked and has(linked) else ("none", None)


def has(key):
    return os.path.isfile(_path(key))


def load(key):
    data = torch.load(_path(key), map_location="cpu", weights_only=True)
    return {"samples": NestedTensor((data["video"], data["audio"]))}


def save(key, latent):
    os.makedirs(folder(), exist_ok=True)
    video, audio = latent["samples"].unbind()
    tmp = _path(key) + ".part"
    torch.save({"video": video.detach().cpu(), "audio": audio.detach().cpu()}, tmp)
    os.replace(tmp, _path(key))
    _prune()


def forget(chunks, settings):
    """The whole video is put together: its parts (and their link files) are no longer needed for a resume."""
    for job in chunks:
        wanted = part_settings(job.compiled.mode, settings)
        key = part_key(job, wanted)
        if has(key):
            os.remove(_path(key))
        if _linked(job, wanted) == key:
            os.remove(_link_path(job, wanted))


def _prune():
    """Parts older than KEEP_DAYS are no run's resume any more."""
    limit = time.time() - KEEP_DAYS * 86400
    for name in os.listdir(folder()):
        path = os.path.join(folder(), name)
        if name.endswith((".pt", ".link")) and os.path.getmtime(path) < limit:
            os.remove(path)
