import subprocess
import sys
from typing import List, Optional, Tuple

from pydantic import root_validator

from ape.__modules__ import __modules__
from ape.logging import CliLogger
from ape.plugins import clean_plugin_name
from ape.utils import BaseInterfaceModel, cached_property, get_package_version, github_client

# Plugins maintained OSS by ApeWorX (and trusted)
CORE_PLUGINS = {p for p in __modules__ if p != "ape"}


def _pip_freeze_plugins() -> List[str]:
    # NOTE: This uses 'pip' subprocess because often we have installed
    # in the same process and this session's site-packages won't know about it yet.
    output = subprocess.check_output([sys.executable, "-m", "pip", "freeze"])
    lines = [
        p
        for p in output.decode().splitlines()
        if p.startswith("ape-") or (p.startswith("-e") and "ape-" in p)
    ]

    new_lines = []
    for package in lines:
        if "-e" in package:
            new_lines.append(package.split(".git")[0].split("/")[-1])
        elif "@" in package:
            new_lines.append(package.split("@")[0].strip())
        elif "==" in package:
            new_lines.append(package.split("==")[0].strip())
        else:
            new_lines.append(package)

    return new_lines


class PluginInstallRequest(BaseInterfaceModel):
    """
    An encapsulation of a request to install a particular plugin.
    """

    name: str
    """The name of the plugin, such as ``trezor``."""

    version: Optional[str] = None
    """The version requested, if there is one."""

    @root_validator(pre=True)
    def validate_name(cls, values):
        if "name" not in values:
            raise ValueError("'name' required.")

        name = values["name"]
        version = values.get("version")

        if version and version.startswith("git+"):
            if f"ape-{name}" not in version:
                # Just some small validation so you can't put a repo
                # that isn't this plugin here. NOTE: Forks should still work.
                raise ValueError("Plugin mismatch with remote git version.")

            version = version

        elif not version:
            # Only check name for version constraint if not in version.
            # NOTE: This happens when using the CLI to provide version constraints.
            for constraint in ("==", "<=", ">=", "@git+"):
                # Version constraint is part of name field.
                if constraint not in name:
                    continue

                # Constraint found.
                name, version = _split_name_and_version(name)
                break

        return {"name": clean_plugin_name(name), "version": version}

    @cached_property
    def package_name(self) -> str:
        """
        Like 'ape-plugin'; the name of the package on PyPI.
        """

        return f"ape-{self.name}"

    @cached_property
    def module_name(self) -> str:
        """
        Like 'ape_plugin' or the name you use when importing.
        """

        return f"ape_{self.name.replace('-', '_')}"

    @cached_property
    def current_version(self) -> Optional[str]:
        """
        The version currently installed if there is one.
        """

        return get_package_version(self.package_name)

    @property
    def install_str(self) -> str:
        """
        The strings you pass to ``pip`` to make the install request,
        such as ``ape-trezor==0.4.0``.
        """

        if self.version and self.version.startswith("git+"):
            # If the version is a remote, you do `pip install git+http://github...`
            return self.version

        # `pip install ape-plugin`
        # `pip install ape-plugin==version`.
        # `pip install "ape-plugin>=0.6,<0.7"`

        version = self.version
        if version and ("=" not in version and "<" not in version and ">" not in version):
            version = f"=={version}"

        return f"{self.package_name}{version}" if version else self.package_name

    @property
    def can_install(self) -> bool:
        """
        ``True`` if the plugin is available and the requested version differs
        from the installed one.  **NOTE**: Is always ``True`` when the plugin
        is not installed.
        """

        requesting_different_version = (
            self.version is not None and self.version != self.current_version
        )
        return not self.is_installed or requesting_different_version

    @property
    def in_core(self) -> bool:
        """
        ``True`` if the plugin is part of the set of core plugins that
        ship with Ape.
        """

        return self.module_name.strip() in CORE_PLUGINS

    @property
    def is_installed(self) -> bool:
        """
        ``True`` if the plugin is installed in the current Python environment.
        """
        ape_packages = [_split_name_and_version(n)[0] for n in _pip_freeze_plugins()]
        return self.package_name in ape_packages

    @property
    def pip_freeze_version(self) -> Optional[str]:
        """
        The version from ``pip freeze`` output.
        This is useful because when updating a plugin, it is not available
        until the next Python session but you can use the property to
        verify the update.
        """

        for package in _pip_freeze_plugins():
            parts = package.split("==")
            if len(parts) != 2:
                continue

            name = parts[0]
            if name == self.package_name:
                version_str = parts[-1]
                return version_str

        return None

    @property
    def is_available(self) -> bool:
        """
        Whether the plugin is maintained by the ApeWorX organization.
        """

        return self.module_name in github_client.available_plugins

    def __str__(self):
        """
        A string like ``trezor==0.4.0``.
        """
        if self.version and self.version.startswith("git+"):
            return self.version

        version_key = f"=={self.version}" if self.version and self.version[0].isnumeric() else ""
        return f"{self.name}{version_key}"


class ModifyPluginResultHandler:
    def __init__(self, logger: CliLogger, plugin: PluginInstallRequest):
        self._logger = logger
        self._plugin = plugin

    def handle_install_result(self, result) -> bool:
        if not self._plugin.is_installed:
            self._log_modify_failed("install")
            return False
        elif result != 0:
            self._log_errors_occurred("installing")
            return False
        else:
            plugin_id = self._plugin.name
            version = self._plugin.pip_freeze_version
            if version:
                # Sometimes, like in editable mode, the version is missing here.
                plugin_id = f"{plugin_id}=={version}"

            self._logger.success(f"Plugin '{plugin_id}' has been installed.")
            return True

    def handle_upgrade_result(self, result, version_before: str) -> bool:
        if result != 0:
            self._log_errors_occurred("upgrading")
            return False

        pip_freeze_version = self._plugin.pip_freeze_version
        if version_before == pip_freeze_version or not pip_freeze_version:
            if self._plugin.version:
                self._logger.info(
                    f"'{self._plugin.name}' already has version '{self._plugin.version}'."
                )
            else:
                self._logger.info(f"'{self._plugin.name}' already up to date.")

            return True
        else:
            self._logger.success(
                f"Plugin '{self._plugin.name}' has been "
                f"upgraded to version {self._plugin.pip_freeze_version}."
            )
            return True

    def handle_uninstall_result(self, result) -> bool:
        if self._plugin.is_installed:
            self._log_modify_failed("uninstall")
            return False
        elif result != 0:
            self._log_errors_occurred("uninstalling")
            return False
        else:
            self._logger.success(f"Plugin '{self._plugin.name}' has been uninstalled.")
            return True

    def _log_errors_occurred(self, verb: str):
        self._logger.error(f"Errors occurred when {verb} '{self._plugin}'.")

    def _log_modify_failed(self, verb: str):
        self._logger.error(f"Failed to {verb} plugin '{self._plugin}.")


def _split_name_and_version(value: str) -> Tuple[str, Optional[str]]:
    if "@" in value:
        parts = [x for x in value.split("@") if x]
        return parts[0], "@".join(parts[1:])

    if not (chars := [c for c in ("=", "<", ">") if c in value]):
        return value, None

    index = min(value.index(c) for c in chars)
    return value[:index], value[index:]
