from t3_content_generation._dial_client import (
    DialClient, Resolution, default_candidates, main_logger, output_dir,
)

# https://developers.openai.com/api/reference/resources/images/methods/generate
# DIAL note: `/images/generations` is a forbidden route; image models answer `/chat/completions` with a
# `custom_content.attachments[]` entry (type image/png, url `files/...`) that is downloaded from the DIAL files API.

PROMPT = "Smiling catdog"
CANDIDATES = default_candidates("gpt-image-2-2026-04-21", "gemini-3.1-flash-image")


def generate(client: DialClient, model: str, prompt: str = PROMPT) -> bytes:
    response = client.chat(model, [{"role": "user", "content": prompt}])
    images = DialClient.attachments(response, "image/")
    if not images:
        raise ValueError(f"no image attachment returned (text: {DialClient.content(response)[:120]!r})")
    return client.download(images[0]["url"])


def main(out_dir: str | None = None, client: DialClient | None = None) -> Resolution:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t2_gpt_image_generation", out))
    resolution = client.resolve("T2 image generation", CANDIDATES, lambda m: generate(client, m))
    if resolution.model:
        target = out / f"t2_catdog_{resolution.model}.png"
        target.write_bytes(resolution.result)
        client.log(f"\n🖼️ Saved {len(resolution.result)} bytes -> {target.name}")
    return resolution


if __name__ == "__main__":
    main()
