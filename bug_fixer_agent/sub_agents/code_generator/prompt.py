"""Prompt for the code generator agent."""

import json
import os


def get_file_content(file_path):
    """Read and return the content of a file."""
    try:
        with open(file_path, "r") as file:
            return file.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def load_data_json():
    """Load the data.json file and extract repository information."""
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    data_json_path = os.path.join(base_dir, "data.json")

    try:
        with open(data_json_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return {"error": f"Error loading data.json: {str(e)}"}


def get_original_file_path():
    """Get the original file path from the config file."""
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    config_file = os.path.join(base_dir, "config", "original_file_path.txt")

    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                return f.read().strip()
        else:
            return os.path.join(base_dir, "qdp.py")
    except Exception as e:
        print(f"Error reading original file path: {e}")
        return os.path.join(base_dir, "qdp.py")


def process_hints_text(text):
    """Process the hints text to escape template variables."""
    return text.replace("id_)", "id_param)")


def escape_template_placeholders(text: str) -> str:
    """
    Escapes specific patterns in the text that might be misinterpreted as
    template placeholders by the downstream templating engine.
    Specifically, it handles occurrences of '{id_}' which can cause KeyErrors
    if 'id_' is not a defined context variable.
    """
    return text.replace("{id_}", "[id_]")


base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
original_file_path = get_original_file_path()
CODE_TO_FIX = get_file_content(original_file_path)

data = load_data_json()
problem_statement = data.get("problem_statement", "No problem statement provided.")
hints_text = data.get("hints_text", "No hints provided.")

processed_problem_statement = escape_template_placeholders(problem_statement)
processed_hints_text = process_hints_text(hints_text)

CODE_GENERATOR_PROMPT = f"""
You are a professional code generator. Your task is to generate code to fix the bugs.

The code is written in Python.

Here is the Python code you need to analyze and fix:

```python
{CODE_TO_FIX}
```
# Problem Statement:
{processed_problem_statement}

# Hints:
{processed_hints_text}

The old buggy code is provided to you in a code block.

# Instructions:
1. The code analyzer has identified issues related to the problem statement above.
2. Your task is to implement the necessary changes to fix these issues.
3. Do not write any comments in the code.
4. You MUST write the entire code again, including all parts that don't need changes.
5. Focus specifically on addressing the issue described in the problem statement.
6. Follow the guidance provided in the hints.
7. Ensure your solution is complete and functional.

Please provide the complete, corrected code as your response.

"""
