"""PostToolUse shim for probe arm A: make the top-level eval session look like a native opus-worker subagent.

Usage (from the arm's hooks/hooks.json): <python> shim.py <hook>
Adds agent_type "opus-worker" and agent_id "probe-"+session_id to the hook input, runs <hook> with this
interpreter, and passes its stdout through unchanged. Only that role check is simulated; matching, the
once-per-agent marker and the text are the real hook's.

EVAL_KAIZEN_PROBE_TMPDIR, when set, becomes the hook's TMPDIR, so each probe run has its own marker namespace even
though every run resumes the same session id. When it is set, one JSON line per call is appended to shim.log there
(tool, file name, whether the hook printed anything), so a calibration run shows that the hook fired.
Never fails the session: any error means no output and exit 0.
"""
import json
import os
import subprocess
import sys


def main():
    try:
        hook = sys.argv[1]
        data = json.load(sys.stdin)
        sid = data.get("session_id")
        if not isinstance(sid, str) or not sid:
            return
        data["agent_type"] = "opus-worker"
        data["agent_id"] = "probe-" + sid
        env = dict(os.environ)
        state = env.get("EVAL_KAIZEN_PROBE_TMPDIR")
        if state:
            env["TMPDIR"] = state
        out = subprocess.run([sys.executable, "-I", hook], input=json.dumps(data), capture_output=True, text=True,
                             env=env, timeout=20).stdout
        sys.stdout.write(out)
        if state:
            path = (data.get("tool_input") or {}).get("file_path")
            with open(os.path.join(state, "shim.log"), "a") as log:
                log.write(json.dumps({"tool": data.get("tool_name"), "file": os.path.basename(str(path or "")),
                                      "emitted": bool(out.strip())}) + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
