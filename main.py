import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from bug_fixer_agent.agent import root_agent


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Bug Fixer Agent non-interactively"
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        "-i",
        type=str,
        help="Input text or file path with bug description",
    )
    input_group.add_argument(
        "--input_file",
        "-f",
        type=str,
        help="File containing the bug description",
    )
    input_group.add_argument(
        "--use_problem_statement",
        "-p",
        action="store_true",
        help="Use the problem_statement from data.json as input",
    )

    parser.add_argument(
        "--original_file",
        "-o",
        type=str,
        help="Path to the original file to be fixed (e.g., widgets.py)",
    )

    return parser.parse_args()


def load_data_json():
    """Load the data.json file and extract repository information."""
    with open("bug_fixer_agent/data.json", "r") as f:
        data = json.load(f)

    return data


def clone_repository(repo, base_commit):
    """Clone the repository at the specified commit in the same directory as main.py."""
    current_dir = os.path.dirname(os.path.abspath(__file__))

    repo_name = repo.split("/")[-1]
    repo_dir = os.path.join(current_dir, repo_name)

    if os.path.exists(repo_dir):
        if os.path.exists(os.path.join(repo_dir, ".git")):
            print(f"Repository already exists at {repo_dir}")

            try:
                current_commit = subprocess.check_output(
                    ["git", "-C", repo_dir, "rev-parse", "HEAD"],
                    universal_newlines=True,
                ).strip()

                if current_commit == base_commit:
                    print(f"Repository is already at the correct commit: {base_commit}")
                    return repo_dir
                else:
                    print(f"Checking out commit {base_commit}")
                    subprocess.run(
                        ["git", "-C", repo_dir, "checkout", base_commit], check=True
                    )
                    return repo_dir
            except subprocess.CalledProcessError:
                print(f"Error checking repository state. Re-cloning repository.")
                shutil.rmtree(repo_dir)
        else:
            print(
                f"Directory {repo_dir} exists but is not a git repository. Removing and re-cloning."
            )
            shutil.rmtree(repo_dir)

    print(f"Cloning repository {repo} at commit {base_commit} to {repo_dir}")

    repo_url = f"https://github.com/{repo}.git"
    subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

    subprocess.run(["git", "-C", repo_dir, "checkout", base_commit], check=True)

    return repo_dir


def save_original_file_path(file_path):
    """Save the original file path to a file that can be read by the code analyser agent."""
    config_dir = os.path.join("bug_fixer_agent", "config")
    os.makedirs(config_dir, exist_ok=True)

    config_file = os.path.join(config_dir, "original_file_path.txt")
    with open(config_file, "w") as f:
        f.write(file_path)

    print(f"Original file path saved to {config_file}")


async def run_agent(input_text, original_file_path=None):
    """Run the agent with the provided input text."""
    runner = InMemoryRunner(agent=root_agent, app_name="bug_fixer")

    session = runner.session_service.create_session(
        app_name="bug_fixer", user_id="user"
    )

    message_text = input_text
    if original_file_path:
        message_text += f"\n\nOriginal file path: {original_file_path}"

    message = types.Content(role="user", parts=[types.Part(text=message_text)])

    responses = []
    async for event in runner.run_async(
        user_id=session.user_id, session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            response_text = "".join(part.text or "" for part in event.content.parts)
            if response_text and not event.partial:
                responses.append(f"[{event.author}]: {response_text}")
                print(f"[{event.author}]: {response_text}")

    return responses


def extract_code_generator_output(responses):
    """Extract the entire output from the code_generator_agent."""
    for response in responses:
        if "[code_generator_agent]:" in response:
            output = response.split("[code_generator_agent]: ", 1)[1].strip()
            return output

    return ""


def extract_code_from_output(output):
    """Extract code from the output, handling different formats."""
    code_match = re.search(r"```python\n(.*?)```", output, re.DOTALL)
    if code_match:
        return code_match.group(1)

    code_match = re.search(r"```\n(.*?)```", output, re.DOTALL)
    if code_match:
        return code_match.group(1)

    if (
        output.strip().startswith("class")
        or output.strip().startswith("def")
        or output.strip().startswith("import")
        or output.strip().startswith('"""')
    ):
        return output

    print("DEBUG - Code generator output:")
    print(output[:500] + "..." if len(output) > 500 else output)

    return output


def clean_code_output(code):
    """Clean up the code output to remove any remaining markdown markers."""
    if code.startswith("```python"):
        code = code[len("```python") :].lstrip()

    if code.startswith("```"):
        code = code[len("```") :].lstrip()

    if code.endswith("```"):
        code = code[: -len("```")].rstrip()

    return code


def remove_docstrings_from_patch(patch_file_path):
    """
    Reads a diff patch file, removes docstring content from added lines,
    and overwrites the file.
    It handles both single-line and multi-line docstrings using
    \"\"\"triple double quotes\"\"\" and '''triple single quotes'''.
    """
    try:
        with open(patch_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Patch file {patch_file_path} not found for docstring removal.")
        return False

    modified_lines = []
    in_multiline_docstring = False
    docstring_quotes = None

    for line_content in lines:
        should_keep_line = True

        if line_content.startswith("+"):
            added_text = line_content[1:]
            stripped_added_text = added_text.lstrip()
            current_line_is_part_of_docstring = False

            if in_multiline_docstring:
                current_line_is_part_of_docstring = True
                if docstring_quotes and docstring_quotes in added_text:
                    in_multiline_docstring = False
                    docstring_quotes = None
            else:
                if (
                    stripped_added_text.startswith('"""')
                    and stripped_added_text.endswith('"""')
                    and len(stripped_added_text) >= 6
                ):
                    current_line_is_part_of_docstring = True
                elif (
                    stripped_added_text.startswith("'''")
                    and stripped_added_text.endswith("'''")
                    and len(stripped_added_text) >= 6
                ):
                    current_line_is_part_of_docstring = True
                elif stripped_added_text.startswith('"""'):
                    current_line_is_part_of_docstring = True
                    in_multiline_docstring = True
                    docstring_quotes = '"""'
                    if docstring_quotes in stripped_added_text[len(docstring_quotes) :]:
                        in_multiline_docstring = False
                        docstring_quotes = None
                elif stripped_added_text.startswith("'''"):
                    current_line_is_part_of_docstring = True
                    in_multiline_docstring = True
                    docstring_quotes = "'''"
                    if docstring_quotes in stripped_added_text[len(docstring_quotes) :]:
                        in_multiline_docstring = False
                        docstring_quotes = None

            if current_line_is_part_of_docstring:
                should_keep_line = False

        if should_keep_line:
            modified_lines.append(line_content)

    try:
        with open(patch_file_path, "w", encoding="utf-8") as f:
            f.writelines(modified_lines)
        print(f"Docstrings removed from {patch_file_path}")
        return True
    except Exception as e:
        print(f"Error writing modified patch file {patch_file_path}: {e}")
        return False


def save_patch_to_jsonl(patch_file_path, instance_id, model_name, output_jsonl_file):
    """
    Reads the processed patch file and saves its content in JSONL format.
    """
    try:
        with open(patch_file_path, "r", encoding="utf-8") as f:
            patch_content = f.read()
    except FileNotFoundError:
        print(f"Error: Patch file {patch_file_path} not found for JSONL conversion.")
        return

    patch_data = {
        "instance_id": instance_id,
        "model_name_or_path": model_name,
        "model_patch": patch_content,
    }

    try:
        with open(output_jsonl_file, "w", encoding="utf-8") as f:
            json.dump(patch_data, f)
            f.write("\n")
        print(f"Patch data saved to {output_jsonl_file}")
    except Exception as e:
        print(f"Error writing to JSONL file {output_jsonl_file}: {e}")


def modify_patch_file(patch_file_path):
    """
    Modifies the patch file header to use the git-style format.
    Replaces the first two lines with git-style diff headers.

    Args:
        patch_file_path: Path to the patch file to modify

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(patch_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_header = [
            "diff --git a/django/forms/widgets.py b/django/forms/widgets.py\n",
            "--- a/django/forms/widgets.py\n",
            "+++ b/django/forms/widgets.py\n",
        ]

        modified_lines = new_header + lines[2:]

        with open(patch_file_path, "w", encoding="utf-8") as f:
            f.writelines(modified_lines)

        print(f"Successfully modified patch file: {patch_file_path}")
        return True

    except Exception as e:
        print(f"Error modifying patch file {patch_file_path}: {e}")
        return False


def main():
    """Main entry point."""
    args = parse_arguments()

    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    data = load_data_json()
    repo = data.get("repo")
    base_commit = data.get("base_commit")

    if not repo or not base_commit:
        print("Error: Repository or base commit information missing in data.json")
        sys.exit(1)

    repo_dir = clone_repository(repo, base_commit)
    print(f"Repository ready at {repo_dir}")

    original_file_path = args.original_file
    if original_file_path:
        if os.path.isabs(original_file_path):
            pass
        else:
            repo_name = repo.split("/")[-1]
            if original_file_path.startswith(
                f"{repo_name}\\"
            ) or original_file_path.startswith(f"{repo_name}/"):
                original_file_path = original_file_path[len(repo_name) + 1 :]

            original_file_path = os.path.join(repo_dir, original_file_path)

        if not os.path.exists(original_file_path):
            print(f"Error: Original file {original_file_path} does not exist")
            sys.exit(1)

        print(f"Using original file: {original_file_path}")
    else:
        print(
            "No original file specified. Using default file from bug_fixer_agent/qdp.py"
        )
        original_file_path = "bug_fixer_agent/widgets.py"

    save_original_file_path(original_file_path)

    if args.input:
        input_text = args.input
    elif args.input_file:
        try:
            with open(args.input_file, "r") as file:
                input_text = file.read()
        except Exception as e:
            print(f"Error reading input file: {e}")
            sys.exit(1)
    elif args.use_problem_statement:
        input_text = data.get("problem_statement", "")
        if not input_text:
            print("Error: No problem_statement found in data.json")
            sys.exit(1)
        print("Using problem_statement from data.json as input")
    else:
        print("Error: No input provided")
        sys.exit(1)

    responses = asyncio.run(run_agent(input_text, original_file_path))

    code_generator_output = extract_code_generator_output(responses)

    code_block = extract_code_from_output(code_generator_output)

    if not code_block:
        print("Error: Could not extract code from code_generator_agent's output")
        debug_file = os.path.join(results_dir, "debug_responses.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            for response in responses:
                f.write(f"{response}\n\n{'='*80}\n\n")
        print(f"Saved raw responses to {debug_file} for debugging")
        sys.exit(1)

    cleaned_code = clean_code_output(code_block)

    output_py_path = os.path.join(results_dir, "output.py")
    patch_diff_path = os.path.join(results_dir, "patch.diff")
    output_jsonl_path = os.path.join(results_dir, "generated.jsonl")

    try:
        with open(output_py_path, "w", encoding="utf-8") as f:
            f.write(cleaned_code)
        print(f"Output has been saved to {output_py_path}")
    except Exception as e:
        print(f"Error writing to {output_py_path}: {e}")
        try:
            with open(output_py_path, "w", encoding="ascii", errors="replace") as f:
                f.write(cleaned_code)
            print(
                f"Output has been saved to {output_py_path} (with some characters replaced)"
            )
        except Exception as e2:
            print(f"Failed to write output file: {e2}")
            sys.exit(1)

    try:
        generate_diff_patch(original_file_path, output_py_path, patch_diff_path)

        if remove_docstrings_from_patch(patch_diff_path):
            if modify_patch_file(patch_diff_path):
                instance_id = data.get("instance_id", "unknown_instance")
                model_name = "gemini-2.5-pro"
                save_patch_to_jsonl(
                    patch_diff_path, instance_id, model_name, output_jsonl_path
                )
            else:
                print(
                    "Skipping JSONL saving due to an error in patch file modification."
                )
        else:
            print("Skipping JSONL saving due to an error in docstring removal.")
        print(f"Diff patch has been saved to {patch_diff_path}")
    except Exception as e:
        print(f"Error generating diff patch: {e}")


def generate_diff_patch(original_file, fixed_file, patch_file):
    """Generate a diff patch between original and fixed files."""
    import difflib

    with open(original_file, "r", encoding="utf-8", errors="replace") as f:
        original_lines = f.readlines()

    with open(fixed_file, "r", encoding="utf-8", errors="replace") as f:
        fixed_lines = f.readlines()

    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=original_file,
        tofile=fixed_file,
        n=3,
    )

    with open(patch_file, "w", encoding="utf-8") as f:
        f.writelines(diff)


if __name__ == "__main__":
    main()
