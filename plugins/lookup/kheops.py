# Copyright 2021 Robin Cordier <robin.cordier@bell.ca>
# Copyright 2017 Craig Dunn <craig@craigdunn.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import sys
import requests
import yaml


from copy import deepcopy
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.template import generate_ansible_template_vars, AnsibleEnvironment, USE_JINJA2_NATIVE

from ansible_collections.barbu_it.ansible_kheops.plugins.plugin_utils.common import DOCUMENTATION_OPTION_FRAGMENT, AnsibleKheops


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

if USE_JINJA2_NATIVE:
    from ansible.utils.native_jinja import NativeJinjaText

DOCUMENTATION = """
    lookup: kheops
    author: Robin Cordier <robin.cordier@bell.ca>
    version_added: "3"
    short_description: read key/values from Kheops
    description:
        - This lookup returns the contents of a Kheops key
        - This is an improved fork of https://github.com/kheops/kheops-ansible-lookup-plugin
        - This fork provides python3 support and more query options
    options:
      _terms:
        description: One or more string terms prefixed by a namespace. Format is `<namespace>/<key>`.
        required: True

""" + DOCUMENTATION_OPTION_FRAGMENT

EXAMPLES = """
- name: Return the value of key
  debug:
    msg: "{{ lookup('kheops', 'default/key') }}"

- name: Return a list of values
  debug:
    msg: "{{ lookup('kheops', 'ansible/yum_packages', 'ansible/yum_repos') }}"

- name: Advanced usage
  debug:
    msg: "{{ lookup('kheops', 'ansible/yum_packages', merge='deep_hash', lookup_type='cascade') }}"

- name: Advanced usage with custom parameters
  debug:
    msg: "{{ lookup('kheops', 'ansible/yum_packages', policy='ansible') }}"

"""

RETURN = """
  _data:
    description:
      - Value of the key, when only one term is searched
  _list:
    description:
      - List of value of the keys, when more than one term is searched
    type: list

"""

from pprint import pprint

# Entry point for Ansible starts here with the LookupModule class
class LookupModule(LookupBase):
    def run(self, terms, variables=None, scope=None, **kwargs):

        self.set_options(direct=kwargs)

        process_scope = self.get_option('process_scope')
        process_results = self.get_option('process_results')
        jinja2_native = kwargs.pop('jinja2_native', self.get_option('jinja2_native'))


        # Start jinja template engine
        if process_scope == 'jinja' or process_results == 'jinja':
            if USE_JINJA2_NATIVE and not jinja2_native:
                templar = self._templar.copy_with_new_env(environment_class=AnsibleEnvironment)
            else:
                templar = self._templar


        # Prepare Kheops instance
        self.config_file = self.get_option('config')
        configs = [
          self.config_file,
          kwargs,
          #{
          #    "instance_log_level": 'DEBUG',
          #    }
          ]
        kheops = AnsibleKheops(configs=configs, display=self._display)

        # Create scope
        if process_scope == 'vars':
            scope = kheops.get_scope_from_host_inventory(variables, scope=None)
        elif process_scope == 'jinja':
            scope = kheops.get_scope_from_jinja(variables, self._templar, scope=None)

        # Transform dict to list for lookup/queries
        ret = []
        for term in terms:
            result = kheops.lookup(
                  keys=term,
                  scope=scope,
              )

            # Render data with Templar
            if process_results == 'jinja':
                with templar.set_temporary_context(available_variables=variables):
                    result = templar.template(result,
                                preserve_trailing_newlines=True,
                                convert_data=False, escape_backslashes=False)

                if USE_JINJA2_NATIVE and not jinja2_native:
                    # jinja2_native is true globally but off for the lookup, we need this text
                    # not to be processed by literal_eval anywhere in Ansible
                    result = NativeJinjaText(result)

            # Return result
            subkey = list(result.keys())[0]
            ret.append(result[subkey])

        return ret
