import json
from pathlib import Path

from app import TicketCreate, mock_triage


def main() -> None:
    cases = json.loads(Path('eval_cases.json').read_text())
    cat_ok = 0
    pri_ok = 0
    print(f'{"case":<28} {"exp_cat":<16} {"got_cat":<16} {"exp_pri":<8} {"got_pri"}')
    for case in cases:
        ticket = TicketCreate(**case['ticket'])
        result = mock_triage(ticket)
        c_match = result.category == case['expected_category']
        p_match = result.priority == case['expected_priority']
        cat_ok += int(c_match)
        pri_ok += int(p_match)
        print(
            f'{case["name"]:<28} {case["expected_category"]:<16} {result.category:<16} '
            f'{case["expected_priority"]:<8} {result.priority}'
            f'  {"✓" if c_match else "×"}/{"✓" if p_match else "×"}'
        )
    n = len(cases)
    print(f'\ncategory accuracy: {cat_ok}/{n} = {cat_ok / n:.0%}')
    print(f'priority accuracy: {pri_ok}/{n} = {pri_ok / n:.0%}')


if __name__ == '__main__':
    main()
