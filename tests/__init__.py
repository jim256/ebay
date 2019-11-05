"""
Provide a few test functions to support mocking request/response data
for API calls.
"""
import json
import typing
import pathlib


def load_test_data(call_type: str, test_name: str) -> typing.Union[dict, str]:
    """Load test data from file named `test_name` in `call_type` folder."""
    filename = pathlib.Path(__file__).parent.absolute() / call_type / test_name
    if call_type == 'auth':
        return json.load(open(f'{filename}.json'))
    if call_type == 'search':
        return json.load(open(f'{filename}.json'))
    elif call_type == 'details':
        return open(f'{filename}.xml').read()
    else:
        raise ValueError(f'Unsupported call_type `{call_type}` for loading test data.')
