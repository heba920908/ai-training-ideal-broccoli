"""Run every T3 step against EPAM DIAL: ``python -m t3_content_generation.run_all [--step t1|t2|...|all]``."""

import argparse

from t3_content_generation.t1 import image_analysis
from t3_content_generation.t2 import gpt_image_edit, gpt_image_generation
from t3_content_generation.t3 import speech_to_text
from t3_content_generation.t4 import text_to_speech
from t3_content_generation.t5 import speech_to_speech

STEPS = {
    "t1": [image_analysis.main],
    "t2": [gpt_image_generation.main, gpt_image_edit.main],
    "t3": [speech_to_text.main],
    "t4": [text_to_speech.main],
    "t5": [speech_to_speech.main],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", default="all", choices=[*STEPS, "all"])
    parser.add_argument("--output-dir", default=None, help="Where images, audio and *.log files are written")
    args = parser.parse_args()
    for name, mains in STEPS.items():
        if args.step in ("all", name):
            for step_main in mains:
                print(f"\n{'=' * 40} {name}: {step_main.__module__} {'=' * 40}")
                step_main(args.output_dir)


if __name__ == "__main__":
    main()
