"""Local demo launcher with an optional hidden API-key prompt."""
import argparse
import getpass
import os
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not args.artifact.is_dir():
        parser.error("Build the retrieval artifact first")
    os.environ["RETRIEVAL_ARTIFACT_DIR"] = str(args.artifact.resolve())
    if not os.environ.get("OPENAI_API_KEY"):
        key = getpass.getpass("OpenAI API key (hidden; blank for retrieval only): ").strip()
        if key:
            os.environ["OPENAI_API_KEY"] = key.replace("\\_", "_")
    uvicorn.run("service_desk.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
