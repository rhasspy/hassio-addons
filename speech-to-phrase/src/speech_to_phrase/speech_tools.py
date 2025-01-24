"""Local speech tools."""

import asyncio
import logging
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_LOGGER = logging.getLogger(__name__)


@dataclass
class SpeechTools:
    """Local speech tools."""

    tools_dir: Path
    kaldi_dir: Path
    openfst_dir: Path
    opengrm_dir: Path
    phonetisaurus_bin: Path
    _extended_env: Optional[Dict[str, Any]] = None

    @staticmethod
    def from_tools_dir(tools_dir: Union[str, Path]) -> "SpeechTools":
        tools_dir = Path(tools_dir).absolute()
        return SpeechTools(
            tools_dir=tools_dir,
            kaldi_dir=tools_dir / "kaldi",
            openfst_dir=tools_dir / "openfst",
            opengrm_dir=tools_dir / "opengrm",
            phonetisaurus_bin=tools_dir / "phonetisaurus",
        )

    @property
    def egs_utils_dir(self):
        return self.kaldi_dir / "utils"

    @property
    def egs_steps_dir(self):
        return self.kaldi_dir / "steps"

    @property
    def extended_env(self) -> Dict[str, str]:
        if self._extended_env is None:
            self._extended_env = os.environ.copy()
            bin_dirs: List[str] = [str(self.kaldi_dir / "bin"), str(self.egs_utils_dir)]
            lib_dirs: List[str] = [str(self.kaldi_dir / "lib")]

            if self.opengrm_dir:
                bin_dirs.append(str(self.opengrm_dir / "bin"))
                lib_dirs.append(str(self.opengrm_dir / "lib"))

            if self.openfst_dir:
                bin_dirs.append(str(self.openfst_dir / "bin"))
                lib_dirs.append(str(self.openfst_dir / "lib"))

            current_path = self._extended_env.get("PATH")
            if current_path:
                bin_dirs.append(current_path)

            current_lib_path = self._extended_env.get("LD_LIBRARY_PATH")
            if current_lib_path:
                lib_dirs.append(current_lib_path)

            self._extended_env["PATH"] = os.pathsep.join(bin_dirs)
            self._extended_env["LD_LIBRARY_PATH"] = os.pathsep.join(lib_dirs)

        return self._extended_env

    async def async_run(self, program: str, args: List[str], **kwargs):
        if "env" not in kwargs:
            kwargs["env"] = self.extended_env

        if "stderr" not in kwargs:
            kwargs["stderr"] = asyncio.subprocess.PIPE

        _LOGGER.debug("%s %s", program, args)
        proc = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdout=asyncio.subprocess.PIPE,
            **kwargs,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_text = f"Unexpected error running command {program} {args}"
            if stderr:
                error_text += f": {stderr.decode()}"
            elif stdout:
                error_text += f": {stdout.decode()}"

            raise RuntimeError(error_text)

        return stdout

    async def async_run_shell(self, cmd: str, **kwargs) -> bytes:
        if "env" not in kwargs:
            kwargs["env"] = self.extended_env

        if "stderr" not in kwargs:
            kwargs["stderr"] = asyncio.subprocess.PIPE

        _LOGGER.debug(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            **kwargs,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_text = f"Unexpected error running command {cmd}"
            if stderr:
                error_text += f": {stderr.decode()}"
            elif stdout:
                error_text += f": {stdout.decode()}"

            raise RuntimeError(error_text)

        return stdout

    async def async_run_pipeline(  # pylint: disable=redefined-builtin
        self, *commands: List[str], input: Optional[bytes] = None, **kwargs
    ) -> bytes:
        if "env" not in kwargs:
            kwargs["env"] = self.extended_env

        if "stderr" not in kwargs:
            kwargs["stderr"] = asyncio.subprocess.PIPE

        if input is not None:
            kwargs["stdin"] = asyncio.subprocess.PIPE

        command_str = " | ".join((shlex.join(c) for c in commands))
        _LOGGER.debug(command_str)

        proc = await asyncio.create_subprocess_shell(
            command_str,
            stdout=asyncio.subprocess.PIPE,
            **kwargs,
        )
        stdout, stderr = await proc.communicate(input=input)
        if proc.returncode != 0:
            error_text = f"Unexpected error running command {command_str}"
            if stderr:
                error_text += f": {stderr.decode()}"
            elif stdout:
                error_text += f": {stdout.decode()}"

            raise RuntimeError(error_text)

        return stdout
