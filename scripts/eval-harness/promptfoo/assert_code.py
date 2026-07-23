import re, subprocess, tempfile, os
def get_assert(output, context):
    test = context['vars'].get('test', '')
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", output, re.DOTALL)
    code = m[-1] if m else output
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 's.py')
        open(p, 'w').write(code + "\n" + test + "\nprint('PASS')\n")
        try:
            r = subprocess.run(['python3', p], capture_output=True, text=True, timeout=15)
            ok = r.returncode == 0 and 'PASS' in r.stdout
            return {'pass': ok, 'score': 1.0 if ok else 0.0,
                    'reason': 'ok' if ok else (r.stderr.strip()[-150:] or 'fail')}
        except Exception as e:
            return {'pass': False, 'score': 0.0, 'reason': str(e)[:150]}
