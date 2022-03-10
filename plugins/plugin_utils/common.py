# -*- coding: utf-8 -*-

import os
import logging
from dataclasses import dataclass
from typing import Any, Union
from copy import deepcopy
import yaml

from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.module_utils.common.text.converters import to_native
from ansible.utils.display import Display
from ansible.template import (
    generate_ansible_template_vars,
    AnsibleEnvironment,
    USE_JINJA2_NATIVE,
)

from kheops.app import Kheops


DOCUMENTATION_OPTION_FRAGMENT = """

      # Plugin configuration
      # ==========================
      config:
        description:
          - Path to Kheops configuration yaml file
          - Can be useful to reuse and merge existing configurations
          - All settings of the target files can be overriden from this file
          - Ignored if blank or Null
        default: Null
        ini:
            - section: inventory
              key: kheops_config
        env:
            - name: ANSIBLE_KHEOPS_CONFIG

      mode:
        description:
          - Choose `client` to use a remote Khéops instance
          - Choose `instance` to use a Khéops directly
        default: 'instance'
        choices: ['instance', 'client']
        env:
            - name: ANSIBLE_KHEOPS_MODE

      # default_namespace:
      #   description:
      #     - The Kheops namespace to use
      #   default: 'default'
      #   env:
      #       - name: ANSIBLE_KHEOPS_DEFAULT_NAMESPACE

      # default_scope:
      #   description:
      #     - A list of default variables to inject in scope.
      #   default: 'default'
      #   env:
      #       - name: ANSIBLE_KHEOPS_DEFAULT_SCOPE


      # Instance configuration (Direct)
      # ==========================
      # Instance configuration
      instance_config:
        description:
          - The Kheops configuration file to use.
          - Require mode=instance
        default: 'site/kheops.yml'
        env:
            - name: ANSIBLE_KHEOPS_INSTANCE_CONFIG
      instance_namespace:
        description:
          - The Kheops configuration file to use.
          - Require mode=instance
        default: 'default'
        env:
            - name: ANSIBLE_KHEOPS_INSTANCE_NAMESPACE
      instance_log_level:
        description:
          - Khéops logging level
          - Require mode=instance
        choices: ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        default: 'WARNING'
        env:
            - name: ANSIBLE_KHEOPS_INSTANCE_LOG_LEVEL
      instance_explain:
        description:
          - Khéops logging explain
          - Require mode=instance
        type: boolean
        default: False
        env:
            - name: ANSIBLE_KHEOPS_INSTANCE_EXPLAIN


      # Instance configuration (Client)
      # ==========================
      # turfu # Client configuration
      # turfu client_token:
      # turfu   description:
      # turfu     - The Kheops token to use to authenticate against Kheops server.
      # turfu   default: ''
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_TOKEN
      # turfu client_host:
      # turfu   description:
      # turfu     - Hostname of the Kheops Server.
      # turfu   default: '127.0.0.1'
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_HOST
      # turfu client_port:
      # turfu   description:
      # turfu     - Kheops port to connect to.
      # turfu   default: '9843'
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_PORT
      # turfu client_protocol:
      # turfu   description:
      # turfu     - The URL protocol to use.
      # turfu   default: 'http'
      # turfu   choices: ['http', 'https']
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_PROTOCOL
      # turfu client_validate_certs:
      # turfu   description:
      # turfu     - Whether or not to verify the TLS certificates of the Kheops server.
      # turfu   type: boolean
      # turfu   default: False
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_VALIDATE_CERTS


      # Query configuration
      # ==========================
      namespace:
        description:
          - The Kheops namespace to use
        default: 'default'
        env:
            - name: ANSIBLE_KHEOPS_DEFAULT_NAMESPACE
      scope:
        description:
          - A hash containing the scope to use for the request, the values will be resolved as Ansible facts.
          - Use a dot notation to dig deeper into nested hash facts.
        default:
          node: inventory_hostname
          groups: group_names

      keys:
        description:
          - A list of keys to lookup
        default: Null


      # Behavior configuration
      # ==========================
      process_scope:
        description:
          - This setting defines how is parsed the `scope` configuration
          - Set `vars` to enable simple variable interpolation
          - Set `jinja` to enable jinja string interpolation
        default: 'jinja'
        choices: ['vars', 'jinja']

      process_results:
        description:
          - This setting defines how is parsed the returned results.
          - Set `none` to disable jinja interpolation from result.
          - Set `jinja` to enable jinja result interpolation.
          - Using jinja may pose some security issues, as you need to be sure that your source of data is properly secured.
        default: 'none'
        choices: ['none', 'jinja']

      jinja2_native:
        description:
            - Controls whether to use Jinja2 native types.
            - It is off by default even if global jinja2_native is True.
            - Has no effect if global jinja2_native is False.
            - This offers more flexibility than the template module which does not use Jinja2 native types at all.
            - Mutually exclusive with the convert_data option.
        default: False
        type: bool
        env:
            - name: ANSIBLE_JINJA2_NATIVE
        notes:
          - Kheops documentation is available on http://kheops.io/
          - You can add more parameters as documented in http://kheops.io/server/api

"""


KEY_NS_SEP = "/"
if USE_JINJA2_NATIVE:
    from ansible.utils.native_jinja import NativeJinjaText


@dataclass
class Key:
    key: str
    remap: Union[str, type(None)]
    namespace: Union[type(None), str]

    def show(self):
        ret = self.key
        if self.namespace is not None:
            ret = f"{self.namespace}{KEY_NS_SEP}{ret}"
        return ret


class AnsibleKheops:
    """Main Ansible Kheops Class"""

    def __init__(self, configs=None, display=None):

        self.configs = configs or []
        self.display = display or Display()

        config = self.get_config()

        # Instanciate Kheops
        if config["mode"] == "instance":

            # Configure logging
            logger = logging.getLogger("kheops")
            logger.setLevel(config["instance_log_level"])

            # See for logging: https://medium.com/opsops/debugging-requests-1989797736cc
            class ListLoggerHandler(logging.Handler):
                def emit(self, record):
                    msg = self.format(record)

            main_logger = logging.getLogger()
            main_logger.addHandler(ListLoggerHandler())
            main_logger.setLevel(logging.DEBUG)

            # Start instance
            self.kheops = Kheops(
                config=config["instance_config"], namespace=config["instance_namespace"]
            )
        elif config["mode"] == "client":
            raise AnsibleError("Kheops client mode is not implemented")

        self.config = config
        self.display.v("Kheops instance has been created")

    def get_config(self):
        """
        Processing order:
        - Fetch the value of config or fallback on ANSIBLE_KHEOPS_CONFIG
        - Load the config if any
        - Overrides with other options
        """

        # Extract default value from doc
        data_doc = yaml.safe_load(DOCUMENTATION_OPTION_FRAGMENT)
        default_config = {
            key: value.get("default", None) for key, value in data_doc.items()
        }

        merged_configs = {}
        for config in self.configs:

            conf_data = None
            if isinstance(config, str):
                self.display.vv("Read Kheops file config %s" % config)
                if os.path.isfile(config):
                    data = open(config, "r", encoding="utf-8")
                    conf_data = yaml.safe_load(data)
                else:
                    raise AnsibleError(f"Unable to find configuration file {config}")

            elif isinstance(config, dict):
                self.display.vv("Read Kheops direct config %s" % config)
                conf_data = config
            elif isinstance(config, type(None)):
                continue
            else:
                assert False, f"Bad config for: {config}"

            assert isinstance(conf_data, dict), f"Bug with conf_data: {conf_data}"
            if isinstance(conf_data, dict):
                merged_configs.update(conf_data)

        # Get environment config
        items = [
            # We exclude 'config'
            "mode",
            "instance_config",
            "instance_namespace",
            "instance_log_level",
            "namespace",
            "scope",
            "keys",
        ]
        env_config = {}
        for item in items:
            envvar = "ANSIBLE_KHEOPS_" + item.upper()
            try:
                env_config[item] = os.environ[envvar]
            except KeyError:
                pass

        # Merge results
        combined_config = {}
        combined_config.update(default_config)
        combined_config.update(env_config)
        combined_config.update(merged_configs)

        return combined_config

    @staticmethod
    def parse_string(item, default_namespace):
        key = None
        remap = key
        namespace = default_namespace

        if isinstance(item, str):

            parts = item.split(KEY_NS_SEP, 3)
            if len(parts) > 0:
                key = parts[0]
            if len(parts) > 1:
                namespace = parts[0]
                key = parts[1]
            if len(parts) > 2:
                remap = parts[2]

        elif isinstance(item, dict):
            key = item.get("key")
            remap = item.get("remap", key)
            namespace = item.get("namespace", namespace)

        return Key(key=key, remap=remap, namespace=namespace)

    @classmethod
    def parse_keys(self, data, namespace):
        keys = []
        if isinstance(data, str):
            keys.append(self.parse_string(data, namespace))

        elif isinstance(data, list):
            for item in data:
                keys.append(self.parse_string(item, namespace))
        elif isinstance(data, dict):
            for key, value in data.items():
                item = key
                if value:
                    assert isinstance(value, str), f"Need a string, got: {value}"
                    item = f"{key}{KEY_NS_SEP}{value}"

                keys.append(self.parse_string(item, namespace))

        else:
            raise AnsibleError(f"Unable to process Kheops keys: {keys}")

        return keys

    def get_scope_from_host_inventory(self, host_vars, scope=None):
        """
        Build scope from host vars
        """
        scope = scope or self.config["scope"]
        ret = {}
        for key, val in scope.items():
            # Tofix should this fail silently ?
            ret[key] = host_vars.get(val, None)

        return ret

    def get_scope_from_jinja(self, host_vars, templar, scope=None, jinja2_native=False):
        """
        Parse in jinja a dict scope
        """
        scope = scope or self.config["scope"]

        if USE_JINJA2_NATIVE and not jinja2_native:
            _templar = templar.copy_with_new_env(environment_class=AnsibleEnvironment)
        else:
            _templar = templar

        _vars = deepcopy(host_vars)
        ret = {}
        with _templar.set_temporary_context(available_variables=_vars):

            for key, value in scope.items():
                res = value
                try:
                    res = _templar.template(
                        value,
                        preserve_trailing_newlines=True,
                        convert_data=True,
                        escape_backslashes=False,
                    )
                    if USE_JINJA2_NATIVE and not jinja2_native:
                        # jinja2_native is true globally but off for the lookup, we need this text
                        # not to be processed by literal_eval anywhere in Ansible
                        res = NativeJinjaText(res)
                    self.display.vvv(f"Transformed scope value: {value} => {res}")
                except AnsibleUndefinedVariable as err:
                    self.display.error(f"Got templating error for string '{value}': {err}")
                    raise err

                ret[key] = res

        return ret

    def lookup(self, keys, namespace=None, scope=None, explain=None):
        """
        Start a lookup query
        """

        if explain is None:
            explain = self.config["instance_explain"]

        namespace = namespace or self.config["namespace"]
        scope = scope or self.config["scope"]
        keys = keys or self.config["keys"]
        keys_config = self.parse_keys(keys, namespace)
        keys = [i.show() for i in keys_config]

        self.display.v(f"Kheops keys: {keys}")
        self.display.vv(f"Kheops scope: {scope}")

        ret = self.kheops.lookup(
            keys=keys,
            scope=scope,
            # trace=True,
            explain=explain,
            namespace_prefix=False
        )

        # Remap output
        for key in keys_config:
            if key.remap is not None and key.remap != key.key:
                ret[key.remap] = ret[key.key]
                del ret[key.key]

        return ret or {}

    def super_lookup(
        self,
        keys,
        namespace=None,
        scope=None,
        kwargs=None,
        _templar=None,
        _variables=None,
        _process_scope=None,
        _process_results=None,
        jinja2_native=False,
    ):
        """
        Lookup method wrapper
        """

        _process_scope = _process_scope or self.config["process_scope"]
        _process_results = _process_results or self.config["process_results"]

        scope = scope or self.config["scope"]
        if _process_scope == "vars":
            scope = self.get_scope_from_host_inventory(_variables, scope=scope)
        elif _process_scope == "jinja":
            assert _templar, f"BUG: We expected a templar object here, got: {_templar}"
            scope = self.get_scope_from_jinja(
                _variables, _templar, scope=scope, jinja2_native=jinja2_native
            )

        ret = self.lookup(keys, namespace=namespace, scope=scope)

        if _process_results == "jinja":
            with _templar.set_temporary_context(available_variables=_variables):
                ret = _templar.template(
                    ret,
                    preserve_trailing_newlines=True,
                    convert_data=False,
                    escape_backslashes=False,
                )
            if USE_JINJA2_NATIVE and not jinja2_native:
                ret = NativeJinjaText(ret)

        return ret
