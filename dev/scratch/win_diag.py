import json, shutil, tempfile
from pathlib import Path
from omnigent.inner.os_env import create_os_environment
from omnigent.tools.builtins.os_env import build_os_env_tools
from omnigent.inner.datamodel import OSEnvSpec, OSEnvSandboxSpec
from omnigent.tools.base import ToolContext

print("which bash:", shutil.which("bash"), "which sh:", shutil.which("sh"))
tmp = Path(tempfile.mkdtemp())
env = create_os_environment(OSEnvSpec(type="caller_process", cwd=str(tmp), sandbox=OSEnvSandboxSpec(type="none")))
print("shell_path:", getattr(env, "shell_path", None) or getattr(env, "_shell_path", None))
shell = {t.name(): t for t in build_os_env_tools(env)}["sys_os_shell"]
ctx = ToolContext(task_id="t", agent_id="a", workspace=tmp)
for cmd in ["printf ok", "echo hi", "exit 3"]:
    print(cmd, "->", shell.invoke(json.dumps({"command": cmd}), ctx)[:1500])
env.close()
