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
  
      enable_jinja:
        description:
            - Enable or not Jinja rendering
        default: True
        version_added: '2.11'
        type: bool
      jinja2_native:
        description:
            - Controls whether to use Jinja2 native types.
            - It is off by default even if global jinja2_native is True.
            - Has no effect if global jinja2_native is False.
            - This offers more flexibility than the template module which does not use Jinja2 native types at all.
            - Mutually exclusive with the convert_data option.
        default: False
        version_added: '2.11'
        type: bool
        notes:
          - Kheops documentation is available on http://kheops.io/
          - You can add more parameters as documented in http://kheops.io/server/api
  
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

        self.process_scope = self.get_option('process_scope')
        self.process_results = self.get_option('process_results')

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
        if self.process_scope == 'vars':
            scope = kheops.get_scope_from_host_inventory(variables, scope=None)
        elif self.process_scope == 'jinja':
            scope = kheops.get_scope_from_jinja(variables, self._templar, scope=None)

        # Transform dict to list for lookup/queries
        ret = []
        for term in terms:
            result = kheops.lookup(
                  keys=term,
                  scope=scope,
              )
            ret.append(result)

        return ret



        # assert isinstance(terms, list), f"Expected a list, got: {terms}"

        # # Parse arguments
        # kwargs = kwargs or {}
        # #enable_jinja = kwargs.pop('enable_jinja', True)
        # #jinja2_native = kwargs.pop('jinja2_native', False)

        # #enable_jinja = kwargs.pop('enable_jinja', True)
        # #jinja2_native = kwargs.pop('jinja2_native', False)

        # self.namespace = self.get_option('query_namespace')
        # self.configuration = self.get_option('configuration')

        # # Instanciate Kheops client
        # kheops = Kheops(config=self.configuration, namespace=self.namespace)

        # for term in terms:
        #     print ("Lookup for key: ", term)
        

        # print ("WIIIIIIIIPPPPPPPPPPPPPPPPP")

        # # Start jinja template engine
        # if enable_jinja:
        #     if USE_JINJA2_NATIVE and not jinja2_native:
        #         templar = self._templar.copy_with_new_env(environment_class=AnsibleEnvironment)
        #     else:
        #         templar = self._templar

        # # Look for each terms
        # ret = []
        # for term in terms:
        #     lookuppath = term.split('/')
        #     key = lookuppath.pop()
        #     namespace = lookuppath

        #     if not namespace:
        #         raise AnsibleError("No namespace given for lookup of key %s" % key)

        #     response = kheops.lookup(key=key, namespace=namespace, variables=variables, kwargs=kwargs)

        #     # Render data with Jinja
        #     if enable_jinja:
        #         # Build a copy of environment vars
        #         vars = deepcopy(variables)

        #         # Render data with Templar
        #         with templar.set_temporary_context(available_variables=vars):
        #             res = templar.template(response['payload'], preserve_trailing_newlines=True,
        #                                        convert_data=False, escape_backslashes=False)

        #         if USE_JINJA2_NATIVE and not jinja2_native:
        #             # jinja2_native is true globally but off for the lookup, we need this text
        #             # not to be processed by literal_eval anywhere in Ansible
        #             res = NativeJinjaText(res)
        #     else:
        #         res = response['payload']

        #     # Append response to response array
        #     ret.append(res)

        # return ret

