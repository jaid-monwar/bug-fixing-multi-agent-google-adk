import base64
import os

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from . import prompt

_END_OF_EDIT_MARK = "---END-OF-EDIT---"


def _remove_end_of_edit_mark(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if _END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1 :]
            part.text = part.text.split(_END_OF_EDIT_MARK, 1)[0]
    return llm_response


# generation_config = types.GenerateContentConfig(
#     temperature=0,
# )

code_analyser_agent = Agent(
    # model="gemini-2.0-flash",
    model="gemini-2.5-pro-preview-05-06",
    name="code_analyser_agent",
    instruction=prompt.CODE_ANALYSER_PROMPT,
    # generate_content_config=generation_config,
    after_model_callback=_remove_end_of_edit_mark,
)
