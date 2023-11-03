# Copyright 2019-2022 DADoES, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License in the root directory in the "LICENSE" file or at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import bpy
import math
from anatools.lib.node import Node
from anatools.lib.generator import CreateBranchGenerator
from anatools.lib.ana_object import AnaObject
import anatools.lib.context as ctx
import numpy as np
import logging
from anatools.lib.file_handlers import file_to_objgen
from toybox.nodes.object_generators import ToyboxChannelObject

logger = logging.getLogger(__name__)

class PlacementOverContainerClass(Node):
    """
    A class to represent the PlacementOverContainer node, a node that places objects in a scene.
    """

    def exec(self):
        """Execute node"""
        logger.info("Executing {}".format(self.name))
        
        object_number = min(200, int(self.inputs["Number of Objects"][0]))

        object_list = []
        objects_input = self.inputs["Object Generators"]
        if objects_input[0] != "":
            #Wrap any file objects in an object generator
            generators = file_to_objgen(self.inputs["Object Generators"], ToyboxChannelObject)
            
            #Set up a branch generator for multiple input objects
            branch_generator = CreateBranchGenerator(generators)

            for ii in np.arange(object_number):
                #Pick a new branch from the inputs and executes it
                this_object = branch_generator.exec()
                object_list.append(this_object)
                #.root is the actual blender object
                this_object.root.location = (
                    0.1*(ctx.random.random()-0.5),
                    0.1*(ctx.random.random()-0.5),
                    2+0.1*ii)
                this_object.root.rotation_euler = (
                    math.radians(ctx.random.uniform(0,360)),
                    math.radians(ctx.random.uniform(0,360)),
                    math.radians(ctx.random.uniform(0,360)))

        drop(object_list, self.inputs)

        return {"Objects of Interest": object_list}


class RandomPlacementClass(Node):
    """
    A class to represent the RandomPlacement node, a node that places objects in a scene.
    """

    def exec(self):
        """Execute node"""
        logger.info("Executing {}".format(self.name))
        
        object_number = min(200, int(self.inputs["Number of Objects"][0]))

        object_list = []
        objects_input = self.inputs["Object Generators"]
        if objects_input[0] != "":
            #Wrap any file objects in an object generator
            generators = file_to_objgen(self.inputs["Object Generators"], ToyboxChannelObject)
            
            #Set up a branch generator for multiple input objects
            branch_generator = CreateBranchGenerator(generators)

            for ii in np.arange(object_number):
                #Pick a new branch from the inputs and executes it
                this_object = branch_generator.exec() 
                object_list.append(this_object)
                
                this_object.root.location = (
                    0.5*(ctx.random.random()-0.5),
                    0.5*(ctx.random.random()-0.5),
                    2+0.1*ii)
                this_object.root.rotation_euler = (
                    math.radians(ctx.random.uniform(0,360)),
                    math.radians(ctx.random.uniform(0,360)),
                    math.radians(ctx.random.uniform(0,360)))

        drop(object_list, self.inputs)

        return {"Objects of Interest": object_list}


def drop(object_list, inputs):
    """
    Apply gravity to objects in a scene, creating a floor and container that do not fall.
    """

    #Let's make sure we have a rigid body world going.
    bpy.ops.rigidbody.world_add()
    sc = bpy.context.scene
    sc.rigidbody_world.enabled = True
    collection = bpy.data.collections.new("CollisionCollection")

    sc.rigidbody_world.collection = collection
    #sc.rigidbody_world.substeps_per_frame = 150 # default 10
    #sc.rigidbody_world.solver_iterations  = 150 # default 10
    
    #Set what frame to use for the image - consider exposing this to the user
    sc.rigidbody_world.point_cache.frame_end = 50 # default 250
    sc.frame_current = 50

    for obj in object_list:
        sc.rigidbody_world.collection.objects.link(obj.root)

    #Create the floor and container - pick a link for each when more than one is provided
    floor_generator = CreateBranchGenerator(file_to_objgen(inputs["Floor Generator"], AnaObject))
    floor = floor_generator.exec()
    sc.rigidbody_world.collection.objects.link(floor.root)
    floor.root.rigid_body.type = 'PASSIVE'
    floor.root.rigid_body.collision_shape = 'MESH'
    floor.root.rigid_body.use_margin = True
    floor.root.rigid_body.collision_margin = 0.001

    container_input = inputs["Container Generator"]
    if container_input[0] != "":
        container_generator = CreateBranchGenerator(file_to_objgen(container_input, AnaObject))
        container = container_generator.exec()
        sc.rigidbody_world.collection.objects.link(container.root)
        container.root.rigid_body.type = 'PASSIVE'
        container.root.rigid_body.collision_shape = 'MESH'
        container.root.rigid_body.use_margin = True
        container.root.rigid_body.collision_margin = 0.001

    #Before we go, let's bake the physics
    #bpy.ops.wm.save_as_mainfile(filepath="scene4baked.blend")
    bpy.ops.ptcache.bake_all()

