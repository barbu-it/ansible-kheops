# -*- coding: utf-8 -*-
# Copyright (c) 2020 Robin Cordier <>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# pylint: disable=raise-missing-from
# pylint: disable=super-with-arguments

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
from pprint import pprint

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


      # Query configuration
      # ==========================
      query_namespace:
        description:
          - The Kheops namespace to use
        default: 'default'
        env:
            - name: ANSIBLE_KHEOPS_NAMESPACE
      query_scope:
        description:
          - A hash containing the scope to use for the request, the values will be resolved as Ansible facts.
          - Use a dot notation to dig deeper into nested hash facts.
        default: {}
      query_keys:
        description:
          - A list of keys to lookup
        default: {}


      # Instance configuration
      # ==========================
      configuration:
        description:
          - Path to Kheops configuration yaml file 
        default: 'kheops.yml'
        env:
            - name: ANSIBLE_KHEOPS_CONFIG
      log_level:
        description:
          - Khéops logging level
        choices: ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        default: 'WARNING'
        env:
            - name: ANSIBLE_KHEOPS_LOG_LEVEL

      # turfu # Client configuration
      # turfu token:
      # turfu   description:
      # turfu     - The Kheops token to use to authenticate against Kheops server.
      # turfu   default: ''
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_TOKEN
      # turfu host:
      # turfu   description:
      # turfu     - Hostname of the Kheops Server.
      # turfu   default: '127.0.0.1'
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_HOST
      # turfu port:
      # turfu   description:
      # turfu     - Kheops port to connect to.
      # turfu   default: '9843'
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_PORT
      # turfu protocol:
      # turfu   description:
      # turfu     - The URL protocol to use.
      # turfu   default: 'http'
      # turfu   choices: ['http', 'https']
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_PROTOCOL
      # turfu validate_certs:
      # turfu   description:
      # turfu     - Whether or not to verify the TLS certificates of the Kheops server.
      # turfu   type: boolean
      # turfu   default: False
      # turfu   env:
      # turfu       - name: ANSIBLE_KHEOPS_VALIDATE_CERTS

      # Uneeded # Misc
      # Uneeded version:
      # Uneeded   description:
      # Uneeded     - Kheops API version to use.
      # Uneeded   default: 1
      # Uneeded   choices: [1]
      # Uneeded   env:
      # Uneeded       - name: ANSIBLE_KHEOPS_VERSION
      # Uneeded cache:
      # Uneeded   description:
      # Uneeded     - Enable Kheops inventory cache.
      # Uneeded   default: false
      # Uneeded   type: boolean
      # Uneeded   env:
      # Uneeded       - name: ANSIBLE_KHEOPS_CACHE
      # Uneeded policy:
      # Uneeded   description:
      # Uneeded     - Kheops policy to use for the lookups.
      # Uneeded   default: 'default'

'''

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

import sys
import os
import logging
from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

#import kheops.app as Kheops
from kheops.app import Kheops

sys.path.append("/home/jez/prj/bell/training/tiger-ansible/ext/kheops")


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
        self._read_config_data(path)

        # Read configuration
        self.keys = self.get_option('query_keys')
        self.scope = self.get_option('query_scope')
        self.namespace = self.get_option('query_namespace')

        self.strict = self.get_option('strict')
        self.configuration = self.get_option('configuration')
        self.log_level = self.get_option('log_level')

        self.cache_enabled = os.environ.get(
                'ANSIBLE_KHEOPS_CACHE',
                str(self.get_option('cache'))
                ).lower() in ('true', '1', 't')


        # Determine cache behavior
        #attempt_to_read_cache = self.cache_enabled and cache

        # Khéops instance
        kheops = Kheops(config=self.configuration, namespace=self.namespace)

        # Khéops log support
        log_level = getattr(logging, self.log_level, 'DEBUG')

        logger = logging.getLogger('kheops')
        logger.setLevel(log_level)

        # See for logging: https://medium.com/opsops/debugging-requests-1989797736cc
        class ListLoggerHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)

        list_logging_handler = ListLoggerHandler()
        main_logger = logging.getLogger()
        main_logger.addHandler(list_logging_handler)
        main_logger.setLevel(logging.DEBUG)

        # from pyinstrument import Profiler
        #profiler = Profiler()
        #profiler.start()

        # Loop over each keys
        for host_name in inventory.hosts:
            host = self.inventory.get_host(host_name)

            # Build the scope
            scope = {}
            host_vars = host.get_vars()
            for key, val in self.scope.items():
                scope[key] = host_vars.get(val, None)
            self.display.vvv(f"Kheops scope for {host.name}: {scope} for keys: {self.keys}")

            # Fetch the results
            ret = kheops.lookup(
                keys=[ key_src for key_dst, key_src in self.keys.items() ],
                scope=scope,
                #trace=True,
                #explain=True,
            )

            # Inject variables into host
            for ansible_key, kheops_key in self.keys.items():
                ansible_value = ret.get(kheops_key)
                host.set_variable(ansible_key, ansible_value)

            # Call constructed inventory plugin methods
            hostvars = self.inventory.get_host(host_name).get_vars()
            self._set_composite_vars(self.get_option('compose'), hostvars, host_name, self.strict)
            self._add_host_to_composed_groups(self.get_option('groups'), hostvars, host_name, self.strict)
            self._add_host_to_keyed_groups(self.get_option('keyed_groups'), hostvars, host_name, self.strict)


        #profiler.stop()
        ##profiler.print()
        #profiler.open_in_browser()

