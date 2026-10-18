"""Task-specific strategy additions; original role rules and schemas stay authoritative."""

CHECKLISTS = {
    "business_analyser": "Check scope, distinguish explanation from lookup and scam assessment, extract each target, check detector metadata, then choose only required fetchers. Ask for clarification when ambiguous.",
    "scam_checker": "Check provenance and missing data, weigh supported warning signs and counter-evidence, then calibrate the label and confidence to the available evidence.",
    "forensic_investigator": "Identify whether this is lookup evidence or a detector result, select relevant supported facts, preserve the detector's verdict and confidence when present, then explain limitations clearly.",
}

# Input/output demonstrations teach decisions without assuming a particular call's
# JSON envelope (FI supports both plain text and structured lookup output).
EXAMPLES = {
    "business_analyser": '''
Input: What is a rug pull?
Output decision: general_question; answer directly; no fetchers or detector.
Input: Show the transaction history of 0x1111111111111111111111111111111111111111.
Output decision: address_info; raw_input type address; requested_fields ["tx_history"].
Input: Is token EXAMPLE a scam? No detector is configured.
Output decision: scam_check; raw_input type token_name; resolve the token, clarify ambiguous matches, then request all four context fields. Do not give a verdict yourself.
''',
    "scam_checker": '''
Input: Contract source is unverified; liquidity and transaction fetchers failed.
Output decision: insufficient_evidence, risk_type unknown; explain that unverified source alone is not proof and unavailable data cannot establish safety or fraud.
Input: Successful liquidity fetch reports 95% liquidity removal within an hour of creation, and successful transaction fetch links the removal to the creator.
Output decision: Evidence supports a likely scam with risk_type rug_pull; cite those observations, calibrate confidence, and avoid certainty or a safety guarantee.
''',
    "forensic_investigator": '''
Input: Detector label scam, confidence 0.68, risk_type rug_pull; evidence reports 95% liquidity removal.
Output explanation: The detector flags a likely rug pull with 68% confidence, citing a 95% liquidity removal. This is an uncertain assessment, not proof.
Input: Lookup requested transactions; transaction fetch failed; tokens were not requested.
Output explanation: Transaction history is unavailable because the fetch failed. Token holdings were not requested. Neither establishes whether the address is safe.
''',
}


def strategy_instruction(agent, strategy):
    common = "\nPrompt strategy: " + strategy + ". Preserve the role rules and required output schema. "
    if strategy == "zero_shot":
        return common + "Perform the task directly without demonstrations. Return only the required final output."
    if strategy == "chain_of_thought":
        return common + "Analyze privately before answering. " + CHECKLISTS[agent] + " Return only the final output and concise evidence-based explanation where requested; do not expose private reasoning. Keep reasoning_trace null if present."
    return common + "Use the following input/output demonstrations as examples of task decisions, not evidence about the current target. Format your actual answer using this call's required schema.\n" + EXAMPLES[agent]


def apply_strategy(messages, agent, strategy):
    """Copy messages so repeated calls cannot accumulate instructions in history."""
    result = [dict(message) for message in messages]
    instruction = strategy_instruction(agent, strategy)
    for message in result:
        if message["role"] == "system":
            message["content"] += "\n" + instruction
            break
    else:
        result.insert(0, {"role": "system", "content": instruction})
    return result
