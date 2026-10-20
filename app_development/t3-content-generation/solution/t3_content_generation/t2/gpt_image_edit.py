from t3_content_generation._dial_client import (
    DialClient, Resolution, asset, default_candidates, main_logger, output_dir,
)

# https://developers.openai.com/api/reference/resources/images/methods/edit
# DIAL note: `/images/edits` (multipart/form-data) is a forbidden route. The image is sent instead as an inline
# base64 DIAL attachment on a chat message, and the edited image comes back as an attachment url.

PROMPT = "Add magical sparkles, a soft glow and a mystical aura around the logo"
CANDIDATES = default_candidates("gpt-image-2-2026-04-21", "gemini-3.1-flash-image")


def edit(client: DialClient, model: str) -> bytes:
    message = {
        "role": "user",
        "content": PROMPT,
        "custom_content": {"attachments": [DialClient.attachment(asset("t2/logo.png"), "image/png")]},
    }
    response = client.chat(model, [message])
    images = DialClient.attachments(response, "image/")
    if not images:
        raise ValueError(f"no image attachment returned (text: {DialClient.content(response)[:120]!r})")
    return client.download(images[0]["url"])


def main(out_dir: str | None = None, client: DialClient | None = None) -> Resolution:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t2_gpt_image_edit", out))
    resolution = client.resolve("T2 image edit", CANDIDATES, lambda m: edit(client, m), input_mime="image/png")
    if resolution.model:
        target = out / f"t2_logo_magic_{resolution.model}.png"
        target.write_bytes(resolution.result)
        client.log(f"\n🖼️ Saved {len(resolution.result)} bytes -> {target.name}")
    return resolution


if __name__ == "__main__":
    main()
