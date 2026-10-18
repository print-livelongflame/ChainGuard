"""Check benchmark scoring without spending tokens or contacting providers."""
import json

from evaluation.cases import CASES
from evaluation.run import score, write_reports
from src.schema import AddressContext, DetectionResult
from evaluation import run
from src.llm_config import AgentTokenLimits, LLMConfig


def test_cases_are_unique_and_evidence_validates():
    assert len({case['id'] for case in CASES}) == len(CASES)
    for case in CASES:
        if 'context' in case:
            AddressContext.model_validate(case['context'])
        if 'result' in case:
            DetectionResult.model_validate(case['result'])


def test_sch_valid_but_wrong_label_fails_objective_score():
    case = next(case for case in CASES if case['id'] == 'sch-empty')
    answer = json.dumps(dict(label='not_scam', risk_type='none', confidence=0.9,
                             evidence=[], explanation='Safe', reasoning_trace=None))
    checks, signature = score(case, answer)
    assert not checks['label']
    assert checks['trace_null']
    assert signature == 'not_scam'


def test_failed_trials_remain_in_denominator_and_review_is_blind(tmp_path):
    rows = [dict(case_id='sch-empty', agent='scam_checker', strategy='zero_shot',
                 repeat=i, valid=valid, checks={'label': valid}, seconds=1,
                 signature='insufficient_evidence' if valid else None)
            for i, valid in enumerate([True, False])]
    write_reports(tmp_path, rows, dict(seed=1, provider='test', model='test', temperature=0.2, repeats=2))
    report = (tmp_path / 'REPORT.md').read_text()
    assert '50.0%' in report
    assert '0.0%' in report  # Failed repeat must not count as a consistent decision.
    assert 'zero_shot' not in (tmp_path / 'blind-review.csv').read_text()
    assert 'zero_shot' in (tmp_path / 'review-key.json').read_text()


def test_live_runner_uses_all_strategies_without_modifying_saved_settings(tmp_path, monkeypatch):
    settings = LLMConfig(token_limits=AgentTokenLimits(scam_checker=321))
    before = settings.model_dump()
    monkeypatch.setattr(run, 'get_llm_settings', lambda: settings)
    monkeypatch.setattr(run, 'CASES', [next(c for c in CASES if c['id'] == 'sch-empty')])
    output = json.dumps(dict(label='insufficient_evidence', risk_type='unknown', confidence=0.1,
                             evidence=[], explanation='Insufficient evidence', reasoning_trace=None))
    observed = []
    def completion(*args, **kwargs):
        active = run.llm_provider._turn_settings.get()
        observed.append(active.agents.scam_checker.prompt_strategy)
        assert active.token_limits.scam_checker == 321
        assert active.agents.scam_checker.temperature == 0.2
        return output, {'input_tokens': 10, 'output_tokens': 10, 'total_tokens': 20}
    monkeypatch.setattr(run.llm_provider, 'complete_with_usage', completion)
    directory = tmp_path / 'run'
    monkeypatch.setattr('sys.argv', ['evaluation.run', '--output', str(directory), '--repeats', '1', '--agents', 'scam_checker'])
    run.main()
    assert set(observed) == set(run.STRATEGIES)
    assert settings.model_dump() == before
    rows = [json.loads(line) for line in (directory / 'trials.jsonl').read_text().splitlines()]
    assert len(rows) == 3 and all(row['valid'] for row in rows)
    assert all(row['max_tokens'] == 321 for row in rows)
    assert all('Prompt strategy: ' + row['strategy'] in row['messages'][0]['content'] for row in rows)
