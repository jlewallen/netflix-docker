#
#
#

import random
import time
import string
import os
import re

from context import *

class Instance:
	def __init__(self, name):
		self.name = name
		self.image = None
		self.ports = None
		self.env = None
		self.command = None
		self.short_id = None
		self.long_id = None
		self.ip = None
		self.running = False
		self.created = False

	@staticmethod
	def new_id(size=6, chars=string.ascii_uppercase + string.digits):
		return ''.join(random.choice(chars) for x in range(size))

	def exists(self, docker):
		if self.short_id is None:
			return False
		try:
			details = docker.inspect_container(self.short_id)
			return True
		except:
			return False
		
	def is_running(self, docker):
		if self.short_id is None:
			return False
		try:
			details = docker.inspect_container(self.short_id)
			return details["State"]["Running"]
		except:
			return False

	def make_params(self):
		params = {
			'image':        self.image,
			'ports':        self.ports,
			'environment':  self.env,
			'command':      self.command,
			'detach':       True,
			'hostname':     self.name,
		}
		return params

	def needs_ip(self):
		return self.ip is not None

	def provision(self, ctx):
		docker = ctx.docker
		if self.exists(docker):
			if self.is_running(docker):
				ctx.info("%s: skipping, %s is running" % (self.name, self.short_id))
				return self.short_id
			else:
				ctx.info("%s: %s exists, starting" % (self.name, self.short_id))
				docker.start(self.short_id)
		else:
			ctx.info("%s: creating instance" % (self.name))
			params = self.make_params()
			container = docker.create_container(**params)
			self.short_id = container['Id']
			docker.start(self.short_id)
			ctx.info("%s: instance started %s" % (self.name, self.short_id))

		# this is all kinds of race condition prone, too bad we
		# can't do this before we start the container
		ctx.info("%s: configuring networking %s" % (self.name, self.short_id))
		self.update(ctx)
		if self.needs_ip():
			if self.has_host_mapping():
				raise Exception("Host port mappings and IP configurations are mutually exclusive.")
			self.configure_networking(ctx, self.short_id, self.long_id, "br0", self.calculate_ip())
		ctx.state.update(self.long_id, self)
		return self.short_id

	def has_host_mapping(self):
		if self.ports is None:
			return False
		for port in self.ports:
			if re.match(r"\d+:", port): return True
		return False

	def calculate_ip(self):
		configured = self.ip
		m = re.match(r"^\+(\d+)", configured)
		if m:
			return Configuration.get_offset_ip(int(m.group(0)))
		return configured

	def configure_networking(self, ctx, short_id, long_id, bridge, ip):
		iface_suffix = Instance.new_id()
		iface_local_name = "pvnetl%s" % iface_suffix
		iface_remote_name = "pvnetr%s" % iface_suffix

		# poll for the file, it'll be created when the container starts
		# up and we should spend very little time waiting
		while True:
			try:
				npsid = open("/sys/fs/cgroup/devices/lxc/" + long_id + "/tasks", "r").readline().strip()
				break
			except IOError:
				ctx.info("%s: waiting for container %s cgroup" % (self.name, short_id))
				time.sleep(0.1)

		ctx.info("%s: configuring %s networking, assigning %s" % (self.name, short_id, ip))

		# strategy from unionize.sh
		commands = [
			"mkdir -p /var/run/netns",
			"rm -f /var/run/netns/%s" % long_id,
      "ln -s /proc/%s/ns/net /var/run/netns/%s" % (npsid, long_id),
      "ip link add name %s type veth peer name %s" % (iface_local_name, iface_remote_name),
      "brctl addif %s %s" % (bridge, iface_local_name),
      "ifconfig %s up" % (iface_local_name),
      "ip link set %s netns %s" % (iface_remote_name, npsid),
      "ip netns exec %s ip link set %s name eth1" % (long_id, iface_remote_name),
      "ip netns exec %s ifconfig eth1 %s" % (long_id, ip)
		]

		for command in commands:
			if os.system(command) != 0:
				raise Exception("Error configuring networking: '%s' failed!" % command)

		self.ip = ip

	def stop(self, ctx):
		docker = ctx.docker
		if self.is_running(docker):
			ctx.info("%s: stopping %s" % (self.name, self.short_id))
			docker.stop(self.short_id)
			return self.short_id

	def kill(self, ctx):
		docker = ctx.docker
		if self.is_running(docker):
			ctx.info("%s: killing %s" % (self.name, self.short_id))
			docker.kill(self.short_id)
			return self.short_id

	def destroy(self, ctx):
		docker = ctx.docker
		if self.created:
			ctx.info("%s: destroying %s" % (self.name, self.short_id))
			docker.remove_container(self.short_id)
			return self.short_id

	def update(self, ctx):
		self.created = self.exists(ctx.docker)
		if self.created:
			details = ctx.docker.inspect_container(self.short_id)
			self.long_id = details['ID']
			self.running = self.is_running(ctx.docker)
			self.started_at = details['State']['StartedAt']
			self.created_at = details['Created']
			self.pid = details['State']['Pid']
			if ctx.state.get(self.long_id):
				self.ip = ctx.state.get(self.long_id).ip
		else:
			self.long_id = None
			self.short_id = None
			self.running = False
			self.started_at = None
			self.created_at = None
			self.pid = None
			self.ip = None

	def to_json(self):
		return {
			"name" : self.name,
			"short_id" : self.short_id,
			"long_id" : self.long_id,
			"ip" : self.ip,
			"running" : self.running,
			"created" : self.created,
			"created_at" : self.created_at,
			"started_at" : self.started_at,
			"pid" : self.pid,
			"start_url" : "/instances/%s/start" % self.name,
			"stop_url" : "/instances/%s/stop" % self.name,
			"destroy_url" : "/instances/%s/destroy" % self.name,
			"kill_url" : "/instances/%s/kill" % self.name
		}