"""Transport-independent orchestration shared by the terminal and HTTP API."""
import json
from pathlib import Path
from uuid import uuid4

from agents.ba import ask_llm, describe_validation_error, parse_ba_response


def run_turn(prompt, history, *, execute, respond, output_root=None,
             on_analysis=None, on_task=None, unique_single_output=True):
    """Keep private BA context and emit only user-facing answers and files."""
    working_history = list(history)
    try:
        analysis = ask_llm(prompt, working_history)
        batch = parse_ba_response(analysis)
    except ValueError as error:
        raise ValueError(describe_validation_error(error)) from error
    history[:] = working_history
    if on_analysis:
        on_analysis(json.loads(analysis))
    multiple = len(batch.tasks) > 1
    request_id = uuid4().hex
    for index, task in enumerate(batch.tasks, 1):
        label = f"Task {index}: {task.request_type}"
        if task.raw_input:
            label += f" - {task.raw_input.value}"
        if on_task and multiple:
            on_task(label)
        output = None
        if output_root is not None and (multiple or unique_single_output):
            output = Path(output_root) / request_id / f"task_{index}.json"

        def reply(message):
            # A transport may normalize file references before storing the reply.
            normalized = respond(str(message), label if multiple else None, output)
            text = normalized if isinstance(normalized, str) else str(message)
            content = f"{label}\n{text}" if multiple else text
            history.append({"role": "assistant", "content": content})

        try:
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
            execute(task, reply, str(output) if output else None)
        except Exception as error:
            reply(f"This task could not be completed: {error}")
