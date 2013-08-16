#
#
#

import json

from group import *

class Manifest:
	def __init__(self, name):
		self.name = name
		self.groups = []

	@staticmethod
	def load(path):
		manifest_cfg = json.load(open(path))
		manifest = Manifest(path)
		for group_name in manifest_cfg:
			group_cfg = manifest_cfg[group_name]
			group = Group(group_name)
			for index, instance_cfg in enumerate(group_cfg):
				instance = Instance("%s-%d" % (group_name, index))
				instance.image = instance_cfg["image"]
				instance.ports = instance_cfg.get("ports")
				instance.env = instance_cfg.get("env")
				instance.command = instance_cfg.get("command")
				instance.ip = instance_cfg.get("ip")
				group.instances.append(instance)
			manifest.groups.append(group)
		return manifest

	def to_json(self):
		return {
			'name' : self.name,
			'groups' : map(lambda g: g.to_json(), self.groups),
			"start_url" : "/manifests/0/start",
			"kill_url" : "/manifests/0/kill",
			"destroy_url" : "/manifests/0/destroy"
		}

	def provision(self, ctx):
		self.update(ctx)
		map(lambda group: group.provision(ctx), self.groups)

	def stop(self, ctx):
		self.update(ctx)
		map(lambda group: group.stop(ctx), self.groups)
		self.update(ctx)
	
	def kill(self, ctx):
		self.update(ctx)
		map(lambda group: group.kill(ctx), self.groups)
		self.update(ctx)
	
	def destroy(self, ctx):
		self.update(ctx)
		map(lambda group: group.destroy(ctx), self.groups)
		self.update(ctx)

	def group(self, name):
		for group in self.groups:
			if group.name == name: return group
		return None
	
	def provisionGroup(self, ctx, name):
		self.group(name).provision(ctx)
		self.update(ctx)

	def killGroup(self, ctx, name):
		self.group(name).kill(ctx)
		self.update(ctx)

	def destroyGroup(self, ctx, name):
		self.group(name).destroy(ctx)
		self.update(ctx)

	def resizeGroup(self, ctx, name, size):
		self.group(name).resize(ctx, size)
		self.update(ctx)

	def update(self, ctx):
		map(lambda group: group.update(ctx), self.groups)
	
	def find_instance(self, name):
		for group in self.groups:
			for instance in group.instances:
				if instance.name == name: return instance
		return None
