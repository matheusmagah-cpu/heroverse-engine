"""Bounded, unofficial Agnes Image 2.5 Flash still generation. A fresh, exact zero-credit quote is mandatory.

Request contract (Pavo's public web client, chunks 9821, 4321, 5334 and 9570 of 2026-10-27, and the public
model-capability-spec for `agnes-image`; see README "Image generation"):
- quote: /v1/aigc/credits/calculate {model_code, outputs: [{count: 1, media_type: "image", resolution}],
  inputs: [{count: 1, media_type: "image"}] per reference} (the client sends no ratio; default resolution "sd");
- stream: /v1/chat/stream {conversation_id, prompt, mode: "generate_image", model, ratio, resolution,
  creative_prompt_json (text block + an image block per reference with source_index), images: [{url, meta_data?}]};
- result: history GenerationSuccess, data.data.results[].url (or image_url) on the fixed Pavo CDN.
Every other image model of the catalog is paid: only `agnes-image` is ever sent. This module never retries a
submission, buys credits, or publishes, and does not fetch the media.
"""
import json
from urllib.error import HTTPError

from client import PavoError
import images
from video import PavoVideoClient, conversation_id, price, shown

IMAGE_MODEL = "agnes-image"  # "Agnes Image 2.5 Flash", tagged Free in mode_support_models?mode_code=generate_image
IMAGE_RATIOS = ("9:16", "2:3", "3:4", "1:1", "4:3", "3:2", "16:9", "21:9")  # agnes-image capability spec
IMAGE_RESOLUTIONS = ("sd", "hd", "uhd")  # labels 1K, 2K, 4K; the client's default is sd
MAX_REFERENCES = 6  # input_image.max_count, role "reference" only
MAX_PROMPT = 10000  # input_text.max_length
IMAGE_PATH = r"/[A-Za-z0-9_./%+-]+\.(?:png|jpg|jpeg|webp)"


class PavoImageClient(PavoVideoClient):
    def __init__(self, token=None, opener=None, guard=None):
        """guard: a quota.QuotaGuard (E124: the daily cap and the stop after failed read-backs); server.py always
        passes one."""
        super().__init__(token, opener)
        self._guard = guard

    def status(self):
        result = super().status()
        result["image_model"] = IMAGE_MODEL
        return result

    def prepare_image(self, prompt, aspect_ratio="9:16", resolution="sd", references=None):
        """Local validation only: (prompt, ratio, resolution, reference images); no network."""
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= MAX_PROMPT:
            raise PavoError("INVALID_PROMPT")
        if self._token and self._token in prompt:
            raise PavoError("CREDENTIAL_IN_PROMPT_REFUSED")
        if aspect_ratio not in IMAGE_RATIOS:
            raise PavoError("INVALID_ASPECT_RATIO")
        if resolution not in IMAGE_RESOLUTIONS:
            raise PavoError("INVALID_IMAGE_RESOLUTION")
        if references is not None and not isinstance(references, (list, tuple)):
            raise PavoError("INPUT_REFERENCES_REFUSED")
        references = list(references or [])
        if not all(isinstance(r, str) for r in references) or len(references) > MAX_REFERENCES:
            raise PavoError("INPUT_REFERENCES_REFUSED")
        return prompt.strip(), aspect_ratio, resolution, [images.image(r) for r in references]

    def quote_image(self, aspect_ratio="9:16", resolution="sd", references=None):
        _, aspect_ratio, resolution, refs = self.prepare_image("Price check", aspect_ratio, resolution, references)
        return self._quote_image(aspect_ratio, resolution, len(refs))

    def _quote_image(self, aspect_ratio, resolution, references):
        body = {"model_code": IMAGE_MODEL,
                "outputs": [{"count": 1, "media_type": "image", "resolution": resolution}]}
        if references:
            body["inputs"] = [{"count": 1, "media_type": "image"} for _ in range(references)]
        data = self._video_json("quote", body)
        if not isinstance(data, dict) or type(data.get("is_estimate")) is not bool:
            raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED")
        exact_credits, credits = price(data.get("required_credits"))
        final_points, _ = price(data.get("final_points"))
        return {"model": IMAGE_MODEL, "aspect_ratio": aspect_ratio, "resolution": resolution,
                "input_images": references, "count": 1,
                "required_credits": credits, "final_points": float(final_points), "is_estimate": data["is_estimate"],
                "zero_cost_confirmed": exact_credits == 0 and final_points == 0 and not data["is_estimate"],
                "permanent_free_access_verified": False}

    def generate_image(self, prompt, aspect_ratio="9:16", resolution="sd", references=None):
        prompt, aspect_ratio, resolution, refs = self.prepare_image(prompt, aspect_ratio, resolution, references)
        if self._guard is not None:   # E124: a 0 quote does not mean the free quota is there; refused before any call
            self._guard.before_generate()
        quote = self._quote_image(aspect_ratio, resolution, len(refs))
        if not quote["zero_cost_confirmed"]:
            # Nothing was uploaded or created; the quoted price is reported, never paid.
            raise PavoError("PAVO_ZERO_CREDIT_QUOTE_REQUIRED required_credits=%s final_points=%s is_estimate=%s"
                            % (shown(quote["required_credits"]), shown(quote["final_points"]),
                               str(quote["is_estimate"]).lower()))
        uploaded = [self._upload(item) for item in refs]
        data = self._video_json("create", {
            "title": json.dumps([{"type": "text", "content": "HeroVerse MCP still"}]),
            "folder_id": "", "kb_strict": False,
        })
        if not isinstance(data, dict):
            raise PavoError("PAVO_CONVERSATION_SCHEMA_CHANGED")
        job = conversation_id(data.get("conversation_id"))
        if self._guard is not None:
            self._guard.submitted(job)
        result = {"conversation_id": job, "model": IMAGE_MODEL, "mode": "generate_image", "ratio": aspect_ratio,
                  "resolution": resolution, "input_images": len(refs), "quoted_credits": 0,
                  "quote": {k: quote[k] for k in ("required_credits", "final_points", "is_estimate")},
                  "retry_submission": False, "published": False}
        blocks = [{"type": "text", "content": prompt}]
        blocks += [{"type": "image", "url": u["url"], "source_index": i} for i, u in enumerate(uploaded, 1)]
        body = {"conversation_id": int(job), "prompt": prompt, "mode": "generate_image", "model": IMAGE_MODEL,
                "ratio": aspect_ratio, "resolution": resolution, "count": 1,
                "creative_prompt_json": json.dumps(blocks)}
        if uploaded:
            body["images"] = uploaded
        try:
            accepted = self._await_start(body, IMAGE_MODEL)
        except Exception as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            # A lost acknowledgement is not a failed job: keep the ID, never resubmit.
            return {**result, "status": "unknown", "submitted": None,
                    "next_action": "Call pavo_image_job with this conversation_id; do not resubmit."}
        return {**result, "status": "submitted" if accepted else "rejected", "submitted": accepted,
                "next_action": "Call pavo_image_job with this conversation_id."}

    def image_job(self, job):
        job, running, status, media, turns = self._history(job, IMAGE_MODEL, IMAGE_PATH, ("url", "image_url"))
        if self._guard is not None:
            self._guard.read_back(job, status, media)
        return {"conversation_id": job, "running": running, "status": status,
                "images": [{"url": m["url"], "width": m["width"], "height": m["height"]} for m in media],
                "turn_count": turns, "published": False,
                "conversation_url": "https://app.pavo-ai.work/chat?conversationId=" + job}
