"""A render part's shot LoRAs (core/shot_loras.py) on its model, each through lora_fit like the turbo LoRA, so a piece that
does not fit a pruned H3 model is left out with one note instead of an error per step."""
import logging
import os
from collections import OrderedDict

from ..core.shot_loras import chunk_loras
from . import lora_fit

log = logging.getLogger(__name__)

# Parts follow each other with the same few LoRAs; reading a file of a few hundred MB for every part would dominate. Kept
# small because the state dicts stay in RAM; ComfyUI's own LoraLoader keeps one.
CACHE_SIZE = 4
_cache = OrderedDict()


def _load(name):
    import comfy.utils
    import folder_paths
    path = folder_paths.get_full_path("loras", name)
    if path is None:
        raise FileNotFoundError("Shot LoRA not installed: %s. Put it in models/loras, or choose another one on the shot." % name)
    key = (path, os.path.getmtime(path))
    if key in _cache:
        _cache.move_to_end(key)
    else:
        _cache[key] = comfy.utils.load_torch_file(path, safe_load=True)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    # a shallow copy: the LoRA converters may rename keys in the dict they get, the tensors are only read
    return dict(_cache[key])


def apply(model, job):
    """`model` with the LoRAs of the shots this part samples; the model itself when there are none."""
    for lora in chunk_loras(job.chunk):
        model, left_out = lora_fit.apply(model, _load(lora.name), lora.strength)
        log.info("[H3 Director] render part %d: shot LoRA %s at %.2f", job.index + 1, lora.name, lora.strength)
        if left_out:
            log.warning("[H3 Director] shot LoRA '%s': %d piece(s) do not fit this model and were left out (%s, ...).",
                        lora.name, len(left_out), left_out[0])
    return model
