import base64

from t3_content_generation._dial_client import (
    DialClient, Resolution, asset, default_candidates, main_logger, output_dir,
)

# https://developers.openai.com/api/docs/guides/images-vision?format=url&lang=curl
# https://developers.openai.com/api/docs/guides/images-vision?format=base64-encoded

IMAGE_URL = "https://a-z-animals.com/media/2019/11/Elephant-male-1024x535.jpg"
PROMPT = "Generate poem based on images"
# Course model `gpt-5.6-terra` is deployed on DIAL with a date suffix; `gpt-4o` is the long-lived fallback.
CANDIDATES = default_candidates("gpt-5.6-terra-2026-07-09", "gpt-4o")


def encode_image(path) -> str:
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def build_messages() -> list[dict]:
    logo_b64 = encode_image(asset("t1/logo.png"))
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": IMAGE_URL}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{logo_b64}"}},
        ],
    }]


def main(out_dir: str | None = None, client: DialClient | None = None) -> Resolution:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t1_image_analysis", out))

    def run(model: str) -> str:
        poem = DialClient.content(client.chat(model, build_messages()))
        if not poem.strip():
            raise ValueError("empty answer")
        return poem

    resolution = client.resolve("T1 image analysis", CANDIDATES, run, input_mime="image/png")
    if resolution.model:
        (out / "t1_poem.md").write_text(f"<!-- model: {resolution.model} -->\n{resolution.result}\n", encoding="utf-8")
        client.log(f"\n📝 Poem ({resolution.model}):\n{resolution.result}")
    return resolution


if __name__ == "__main__":
    main()
