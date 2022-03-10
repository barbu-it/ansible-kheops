# -*- coding: utf-8 -*-
# Copyright (c) 2020 Robin Cordier <>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# pylint: disable=raise-missing-from
# pylint: disable=super-with-arguments

from __future__ import (absolute_import, division, print_function)
# __metaclass__ = type

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable
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
        self._consume_options(config_data)

        # Get options from inventory
        self.jinja2_native = self.get_option('jinja2_native')
        self.strict = self.get_option('strict')
        self.compose = self.get_option('compose')

        self.groups = self.get_option('groups')
        self.keyed_groups = self.get_option('keyed_groups')

        # self.process_scope = self.get_option('process_scope')
        # self.process_results = self.get_option('process_results')

        # Prepare Kheops instance
        self.config_file = self.get_option('config')
        ansible_config = {
                "instance_namespace": self.get_option('instance_namespace'),
                "instance_log_level": self.get_option('instance_log_level'),
                "instance_explain": self.get_option('instance_explain'),
                }
        configs = [
            ansible_config,
            self.config_file,
            path,
            ]
        kheops = AnsibleKheops(configs=configs, display=self.display)

        # Loop over each hosts
        for host_name in inventory.hosts:
            host = self.inventory.get_host(host_name)

            ret = kheops.super_lookup(
                keys=None,
                scope=None,
                _templar=self.templar,
                _variables=host.get_vars(),
                jinja2_native=self.jinja2_native,
                #trace=True,
                #explain=True,
            )

            # Inject variables into host
            for key, value in ret.items():
                self.display.vv (f"Define variable for {host_name}: {key}={value}")
                host.set_variable(key, value)

            # Call constructed inventory plugin methods
            hostvars = self.inventory.get_host(host_name).get_vars()
            self._set_composite_vars(self.compose, hostvars, host_name, self.strict)
            self._add_host_to_composed_groups(self.groups, hostvars, host_name, self.strict)
            self._add_host_to_keyed_groups(self.keyed_groups, hostvars, host_name, self.strict)

