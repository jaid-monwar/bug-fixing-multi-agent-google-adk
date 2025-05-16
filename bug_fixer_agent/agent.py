import os

from dotenv import load_dotenv
from google.adk.agents import SequentialAgent

from .sub_agents.code_analyser import code_analyser_agent
from .sub_agents.code_generator import code_generator_agent

load_dotenv()

# Set up credentials explicitly (Uncomment ONLY when using Google Cloud Vertex AI)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "bug_fixer_agent/sa-key.json"

orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    description=(
        "Orchestrates the bug fixing process by first analyzing code issues "
        "through the code_analyser_agent and then generating fixed code via "
        "the code_generator_agent. Results are saved to the 'results' directory."
    ),
    sub_agents=[code_analyser_agent, code_generator_agent],
)

root_agent = orchestrator_agent
