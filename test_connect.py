from runners.openclaw_runner import run_openclaw_session
t = run_openclaw_session('test', 'Say hello in one word.')
print('status:', t['status'])
print('error:', t.get('error'))
print('response:', t['final_response'][:80])
