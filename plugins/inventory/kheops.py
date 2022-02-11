# -*- coding: utf-8 -*-
# Copyright (c) 2020 Robin Cordier <>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# pylint: disable=raise-missing-from
# pylint: disable=super-with-arguments

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys
import os
import logging

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

#sys.path.append("/home/jez/prj/bell/training/tiger-ansible/ext/kheops")
from ansible_collections.barbu_it.ansible_kheops.plugins.plugin_utils.common import DOCUMENTATION_OPTION_FRAGMENT, AnsibleKheops

DOCUMENTATION = '''
    name: kheops
    plugin_type: inventory
    short_description: Kheops host classifier
    requirements:
        - requests >= 1.1
    description:
        - This plugin does not create hosts, but it assign new variables from Kheops to hosts
        - The main usecase of this plugin is to act as a node
        - Get host variables from Kheops (http://kheops.io/)
        - 
        - This plugin get all hosts from inventory and add lookep up keys
        - It's important to make this inventory source loaded after all other hosts has been declared. To force whit behavior, you can name your inventory file by `zzz_` to be sure it will be the last one to be parsed
    extends_documentation_fragment:
        - inventory_cache
        - constructed
    options:

      plugin:
        description: token that ensures this is a source file for the C(kheops) plugin.
        required: True
        choices: ['kheops', 'barbu_it.ansible_kheops.kheops']
''' + DOCUMENTATION_OPTION_FRAGMENT

EXAMPLES = '''
# zzz_dev.kheops.yml
plugin: kheops
host: 127.0.0.1
token: xxx:yyy
query_scope:
  fqdn: inventory_hostname


# zzz_prod.kheops.yml
plugin: kheops
host: kheops.domain.tld
protocol: https
token: xxx:yyy
query_scope:
  fqdn: inventory_hostname
  hostgroup: foreman_hostgroup_title
  organization: foreman_organization_name
  location: foreman_location_name
  environment: foreman_environment_name
'''

from pprint import pprint


class InventoryModule(BaseInventoryPlugin, Cacheable, Constructable):
    NAME = 'kheops'

    def verify_file(self, path):
        valid = False
        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('kheops.yaml', 'kheops.yml')):
                valid = True
        return valid

    def parse(self, inventory, loader, path, cache):
        '''Return dynamic inventory from source '''

        super(InventoryModule, self).parse(inventory, loader, path, cache)
        config_data = self._read_config_data(path)
        #self._consume_options(config_data)

        self.strict = self.get_option('strict')

        self.compose = self.get_option('compose')
        self.groups = self.get_option('groups')
        self.keyed_groups = self.get_option('keyed_groups')

        
        self.config_file = self.get_option('config')

        configs = [
          self.config_file,
          path,
          ]
        kheops = AnsibleKheops(configs=configs, display=self.display)

        # Loop over each keys
        for host_name in inventory.hosts:
          host = self.inventory.get_host(host_name)

          scope = kheops.get_scope_from_host_inventory(host.get_vars(), scope=None)

          # Fetch the results
          ret = kheops.lookup(
              keys=None,
              scope=scope,
              #trace=True,
              #explain=True,
          )

          # Inject variables into host
          for key, value in ret.items():
              self.display.vv (f"Set {host_name} var: {key}={value}")
              host.set_variable(key, value)

          # Call constructed inventory plugin methods
          #hostvars = self.inventory.get_host(host_name).get_vars()
          hostvars = host.get_vars()

          #tutu = hostvars.get('tiger_profiles', "MISSSSINGGGG")
          #print ("YOOOOO", tutu, self.keyed_groups, host_name, self.strict)


          self._set_composite_vars(self.compose, hostvars, host_name, self.strict)
          self._add_host_to_composed_groups(self.groups, hostvars, host_name, self.strict)
          self._add_host_to_keyed_groups(self.keyed_groups, hostvars, host_name, self.strict)

