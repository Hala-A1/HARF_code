# Application tests

All maintained automated test cases are grouped here. Backend and frontend tests
remain separate because Python and JavaScript use different runtimes. No test
cases were removed. `moved-files.json` records every previous location.

From the project root:

```powershell
npm test
backend/.venv/Scripts/python.exe TEST/run_backend.py
backend/.venv/Scripts/python.exe TEST/run_backend.py test_access_requests.py
```

The backend runner selects local storage and offline inference before imports.
Oracle tests use mocks or explicit test fixtures. Do not run the suite against
your live Oracle credentials. Tests that verify historic source preservation
still require the existing private `output/` source archives.

Instruction files whose names contain “test” are content fixtures, not executable
tests, and stay in their channel instruction folders.
