import base64
import logging
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image

import config

logger = logging.getLogger(__name__)

IMG_HEIGHT = 300
IMG_WIDTH = 300
ROW_COUNT = 3


def create_panoramic_view(
    query_image_path: str,
    retrieved_image_paths: list[str],
    output_path: str,
) -> str:
    """Build panoramic comparison image per Milvus multimodal RAG tutorial."""
    panoramic_width = IMG_WIDTH * ROW_COUNT
    panoramic_height = IMG_HEIGHT * ROW_COUNT
    panoramic_image = np.full(
        (panoramic_height, panoramic_width, 3), 255, dtype=np.uint8
    )

    query_panel = np.full((panoramic_height, IMG_WIDTH, 3), 255, dtype=np.uint8)
    query_rgb = np.array(Image.open(query_image_path).convert("RGB"))
    resized_query = cv2.resize(query_rgb[:, :, ::-1], (IMG_WIDTH, IMG_HEIGHT))

    border_size = 10
    blue = (255, 0, 0)
    bordered_query = cv2.copyMakeBorder(
        resized_query,
        border_size,
        border_size,
        border_size,
        border_size,
        cv2.BORDER_CONSTANT,
        value=blue,
    )
    query_panel[IMG_HEIGHT * 2 : IMG_HEIGHT * 3, 0:IMG_WIDTH] = cv2.resize(
        bordered_query, (IMG_WIDTH, IMG_HEIGHT)
    )
    cv2.putText(
        query_panel,
        "query",
        (10, IMG_HEIGHT * 3 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        blue,
        2,
        cv2.LINE_AA,
    )

    for index, image_path in enumerate(retrieved_image_paths[: ROW_COUNT * ROW_COUNT]):
        try:
            rgb = np.array(Image.open(image_path).convert("RGB"))
            bgr = rgb[:, :, ::-1]
        except Exception:
            continue
        resized = cv2.resize(bgr, (IMG_WIDTH - 4, IMG_HEIGHT - 4))
        row = index // ROW_COUNT
        col = index % ROW_COUNT
        start_row = row * IMG_HEIGHT
        start_col = col * IMG_WIDTH
        bordered = cv2.copyMakeBorder(
            resized, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )
        panoramic_image[
            start_row : start_row + IMG_HEIGHT, start_col : start_col + IMG_WIDTH
        ] = bordered
        cv2.putText(
            panoramic_image,
            str(index),
            (start_col + 10, start_row + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    combined = np.hstack([query_panel, panoramic_image])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), combined)
    return str(out)


class LLMReranker:
    """GPT-4o generative reranker with panoramic visual context."""

    def __init__(self) -> None:
        self.api_key = config.OPENAI_API_KEY
        self.model = config.OPENAI_RERANK_MODEL
        self.api_base = config.OPENAI_API_BASE.rstrip("/")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key) and config.MULTIMODAL_RERANK_ENABLED

    def rerank(
        self,
        combined_image_path: str,
        instruction: str,
        product_infos: list[str] | None = None,
    ) -> tuple[list[int], str]:
        if not self.is_available:
            raise RuntimeError(
                "LLM reranker is not configured. Set OPENAI_API_KEY and "
                "MULTIMODAL_RERANK_ENABLED=true."
            )

        with open(combined_image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        prompt = (
            "You are responsible for ranking results for a Composed Image Retrieval. "
            "The user retrieves an image with an 'instruction' indicating their retrieval intent. "
            "For example, if the user queries a red car with the instruction 'change this car to blue,' "
            "a similar type of car in blue would be ranked higher in the results. "
            "Now you would receive instruction and query image with blue border. "
            "Every item has its red index number in its top left. Do not misunderstand it. "
            f"User instruction: {instruction}\n\n"
        )
        if product_infos:
            for index, info in enumerate(product_infos):
                prompt += f"{index}. {info}\n"

        prompt += (
            "Provide a new ranked list of indices from most suitable to least suitable, "
            "followed by an explanation for the top 1 most suitable item only. "
            "The format of the response has to be 'Ranked list: []' with the indices in brackets "
            "as integers, followed by 'Reasons:' plus the explanation why this most fits the "
            "user's query intent."
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 300,
        }

        response = requests.post(
            f"{self.api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]

        start_idx = result.find("[")
        end_idx = result.find("]")
        if start_idx == -1 or end_idx == -1:
            raise ValueError(f"Could not parse ranked list from LLM response: {result}")

        ranked_indices_str = result[start_idx + 1 : end_idx].split(",")
        ranked_indices = [int(index.strip()) for index in ranked_indices_str if index.strip()]
        explanation = result[end_idx + 1 :].strip()
        return ranked_indices, explanation
