"""Prompt for the code analyser agent."""

import json
import os
import re


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
            return os.path.join(base_dir, "widgets.py")
    except Exception as e:
        print(f"Error reading original file path: {e}")
        return os.path.join(base_dir, "widgets.py")


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
CODE_TO_ANALYZE = get_file_content(original_file_path)

data = load_data_json()
problem_statement = data.get("problem_statement", "No problem statement provided.")
hints_text = data.get("hints_text", "No hints provided.")

processed_problem_statement = escape_template_placeholders(problem_statement)
processed_hints_text = process_hints_text(hints_text)

CODE_ANALYSER_PROMPT = f"""
You are a professional code analyser. Your task is to analyse the code and provide a report on the code quality.

The code is written in Python.

Here is the Python code you need to analyze and fix:

```python
{CODE_TO_ANALYZE}
```

# Problem Statement:
{processed_problem_statement}


# Hints:
{processed_hints_text}

Please analyze the code and suggest fixes only for the specific issue described in the problem statement. 
Focus on addressing the exact problem only rather than general code improvements.

You are going to suggest changes to the code to fix only the changes described in the problem statement.
"""
