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
import mathutils
import anatools.lib.context as ctx
from anatools.lib.node import Node
from anatools.lib.scene import AnaScene
import logging
import imageio
import math
import os
import numpy
import glob

logger = logging.getLogger(__name__)

class LightNode(Node):
    """
    A class to represent a the Light node, a node that crates a lamp in the scene.
    """

    def exec(self):
        """Execute node"""
        logger.info("Executing {}".format(self.name))
        lightName = self.name
        # Get the light data
        lightType = self.inputs["Type"][0]
        lightEnergy = float(self.inputs["Radiant Power (W)"][0])
        lightData = bpy.data.lights.new(lightName, type=lightType)
        lightData.energy = lightEnergy
        logging.info("Light Config.. \n" + '\n'.join([f'\t{k}: {getattr(lightData, k)}' for k in dir(lightData) if '__' not in k]))

        #Instantiate the light
        lightLocation = self.inputs["Location (m)"][0]
        if type(lightLocation)==str:
            lightLocation = [float(v) for v in lightLocation.replace('[','').replace(']','').split(',')]
        
        lightObject = bpy.data.objects.new(lightName, lightData)
        lightObject.location = lightLocation
        
        #Point the light at the center (for spot lights)
        point_at(lightObject, mathutils.Vector((0,0,0)))

        return {'Light': lightObject}


class CameraNode(Node):
    """
    A class to represent a the Camera node, a node that crates a camera in the scene.
    """

    def exec(self):
        """Execute node"""
        logger.info("Executing {}".format(self.name))
        
        #Set up camera configuration data
        cameraName = self.name
        cameraData = bpy.data.cameras.new(cameraName)
        logging.info("Camera Config.. \n" + '\n'.join([f'\t{k}: {getattr(cameraData, k)}' for k in dir(cameraData) if '__' not in k]))
        
        #Instantiate the camera object
        cameraObject = bpy.data.objects.new(cameraName, cameraData)
        
        # Set the camera location - constrained to an altitude angle > 45 degrees
        height = float(self.inputs["Location Height (m)"][0])
        height_limits = (0.4, 0.7)
        if height == "<random>":
            height = ctx.random.uniform(height_limits[0], height_limits[1])
        x = ctx.random.uniform(0, height)
        y_limit = math.sqrt(height**2 - x**2)
        y=ctx.random.uniform(-y_limit, y_limit)
        cameraObject.location = (x, y, height)
        
        #Set the camera rotation
        roll = self.inputs["Roll (degrees)"][0]
        point_at(cameraObject, (0,0,0), roll=roll*3.14/180)
        
        return {'Camera': cameraObject}


class RenderNode(Node):
    """
    A class to represent a the Render node, a node that renders an image of the given scene.
    Executing the Render node creates an image, annotation, and metadata file.
    """

    def exec(self):
        """Execute node"""
        #return {}  # testing the time to bake the physics
        logger.info("Executing {}".format(self.name))

        #Get the reference to the blender scene
        scn = bpy.context.scene

        #We do not expect more than one DropObjects node to be ported to here, but the input is still a list.
        objects = self.inputs["Objects of Interest"][0]

        #Add lighting to the scene
        lights = self.inputs["Lights"]
        if lights[0] != "":
            for l in lights:
                scn.collection.objects.link(l)
        #bpy.context.scene.world.light_settings.use_ambient_occlusion = True

        #Add a camera to the scene
        camera = self.inputs["Camera"][0]
        scn.collection.objects.link(camera)
        scn.camera = camera

        #Set the render resolution
        # Set up the camera configuration data
        
        res = self.inputs["Resolution (px)"][0]
        if type(res)==str:
            res = [int(v) for v in res.replace('[','').replace(']','').split(',')]
        scn.render.resolution_x = res[0]
        scn.render.resolution_y = res[1]
        #bpy.ops.object.visual_transform_apply()

        #Initialize an AnaScene.  This configures the Blender compositor and provides object annotations and metadata.
        #To create an AnaScene we need to send a blender scene and a view layer for annotations
        sensor_name = 'RGBCamera'
        scene = AnaScene(
            blender_scene=scn,
            annotation_view_layer=bpy.context.view_layer,
            objects=objects,
            sensor_name=sensor_name)

        #Configure the compositor to include a denoise node for the image
        s = bpy.data.scenes[ctx.channel.name]
        c_rl = s.node_tree.nodes['Render Layers']
        c_c = s.node_tree.nodes['Composite']
        c_dn = s.node_tree.nodes.new('CompositorNodeDenoise')
        s.node_tree.nodes.remove(s.node_tree.nodes['imgout'])
        c_of = s.node_tree.nodes.new('CompositorNodeOutputFile')
        c_of.base_path = os.path.join(ctx.output,'images')
        c_of.file_slots.clear()
        compositeNodeFieldName = f'{ctx.interp_num:010}-#-{sensor_name}.png'
        c_of.file_slots.new(compositeNodeFieldName)
        s.node_tree.links.new(c_rl.outputs['Image'], c_dn.inputs['Image'])
        s.node_tree.links.new(c_dn.outputs['Image'], c_c.inputs['Image'])
        s.node_tree.links.new(c_dn.outputs['Image'], c_of.inputs[compositeNodeFieldName])

        #Render the image
        if ctx.preview:
            logger.info("LOW RES Render for Preview")
            render(resolution='preview')
            imgfilename = f"{ctx.interp_num:010}-{scn.frame_current}-{sensor_name}.png"
            preview = imageio.imread(os.path.join(ctx.output,'images',imgfilename))
            imageio.imsave(os.path.join(ctx.output,'preview.png'), preview)
            return{}

        #bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.getcwd(),"scene4render.blend"))
        render()        

        #Prepare for annotataions
        for obj in objects:
            obj.setup_mask()
        
        collect_depth = self.inputs["Collect Depth and Normal Masks"][0]
        if collect_depth == 'T':
            #Configure compositor to write a depth and normal mask
            #Add the Z and normal pass veiw layers
            bpy.context.scene.view_layers["ViewLayer"].use_pass_z = True
            bpy.context.scene.view_layers["ViewLayer"].use_pass_normal = True
            #Connect the depth render layer to a file output node - normalize this for viewing purposes
            c_normalize = s.node_tree.nodes.new("CompositorNodeNormalize")
            depthOutFieldName = f'{ctx.interp_num:010}-#-{sensor_name}-depth.png'
            c_output_depth = s.node_tree.nodes.new('CompositorNodeOutputFile')
            c_output_depth.base_path = os.path.join(ctx.output,'masks')
            c_output_depth.file_slots.clear()
            c_output_depth.file_slots.new(depthOutFieldName)
            s.node_tree.links.new(c_rl.outputs["Depth"], c_normalize.inputs['Value'])
            s.node_tree.links.new(c_normalize.outputs['Value'], c_output_depth.inputs[depthOutFieldName])
            #Connect the normal render layer to a file output
            #c_normalize = s.node_tree.nodes.new("CompositorNodeNormalize")
            normalOutFieldName = f'{ctx.interp_num:010}-#-{sensor_name}-normal.png'
            c_output_normal = s.node_tree.nodes.new('CompositorNodeOutputFile')
            c_output_normal.base_path = os.path.join(ctx.output,'masks')
            c_output_normal.file_slots.clear()
            c_output_normal.file_slots.new(normalOutFieldName)
            # s.node_tree.links.new(c_rl.outputs["Normal"], c_normalize.inputs['Value'])
            # s.node_tree.links.new(c_normalize.outputs['Value'], c_output_depth.inputs[normalOutFieldName])
            s.node_tree.links.new(c_rl.outputs["Normal"], c_output_normal.inputs[normalOutFieldName])    

        #Remove link to image output file
        s = bpy.data.scenes[ctx.channel.name]
        c_of = s.node_tree.nodes['File Output']
        c_of.file_slots.clear()
        
        #Write masks
        #bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.getcwd(),"compositor4masks.blend"))
        render(resolution='masks')
        
        #You can re-link the output image file node if blender is needed to render the image again
        # c_of.file_slots.new(f'{ctx.interp_num:010}-#-{sensor_name}.png')
        # s.node_tree.links.new(c_dn.outputs[0], c_of.inputs[0])

        calculate_obstruction = self.inputs["Calculate Obstruction"][0]        
        if calculate_obstruction == 'F':
            # Create annotations 
            scene.write_ana_annotations()
            scene.write_ana_metadata()
            return {}
        
        #Render masks for each object (only render a mask file for objects in the image)

        #Unlink all the object masks in the compositor
        links = scn.node_tree.links
        masknodes = [node for node in scn.node_tree.nodes if node.name.split('_')[-1]=='mask']
        masklinks = {}
        for masknode in masknodes:
            masklinks[masknode.index] = {
                'masknode': masknode,
                'socketinput': masknode.outputs[0].links[0].to_socket
            }
            links.remove(masknode.outputs[0].links[0])
        #Unlink the image from the compositor
        for link in scn.node_tree.nodes['Render Layers'].outputs['Image'].links:
            links.remove(link)

        masktemplate = os.path.join(scene.maskout.base_path,
                                    scene.maskout.file_slots[0].path + '.' + scene.maskout.format.file_format.lower())

        #Only render a mask file for objects in the image
        compositemaskfile = masktemplate.replace('#', str(scn.frame_current))
        compimg = imageio.imread(compositemaskfile)
        allmasks = compimg[numpy.nonzero(compimg)]
        renderedobjectidxs = numpy.unique(allmasks)
        renderedobjects = [obj for obj in objects if obj.instance in renderedobjectidxs]

        #Hide all but a single object and render a mask
        for obj in objects:
            obj.root.hide_render = True
            if obj not in renderedobjects:
                obj.rendered = False

        imgpath = scene.imgout.file_slots[0].path
        maskpath = scene.maskout.file_slots[0].path
        for obj in renderedobjects:
            obj.solo_mask_id = f'obj{obj.instance:03}'
            scene.maskout.file_slots[0].path = '{}-{}'.format(maskpath, obj.solo_mask_id)
            scene.imgout.file_slots[0].path = '{}-{}'.format(imgpath, obj.solo_mask_id)

            obj.root.hide_render = False

            # link the ID mask node to it's divide node
            masknode = masklinks[obj.instance]['masknode']
            socketinput = masklinks[obj.instance]['socketinput']
            links.new(masknode.outputs['Alpha'], socketinput)

            render(resolution='low')

            # rehide object
            obj.root.hide_render = True
            links.remove(masknode.outputs[0].links[0])

        #Create annotations
        scene.write_ana_annotations(calculate_obstruction=calculate_obstruction)
        scene.write_ana_metadata()

        logging.info("Number Objects Rendered: {}".format(len([o for o in objects if o.rendered])))

        #Clean up extra rendered files
        maskpattern = os.path.join(scene.maskout.base_path, maskpath.replace('#', str(scn.frame_current)))
        for filepath in glob.glob('{}-*'.format(maskpattern)):
            os.remove(filepath)
        imgpattern = os.path.join(scene.imgout.base_path, imgpath.replace('#', str(scn.frame_current)))
        for filepath in glob.glob('{}-*'.format(imgpattern)):
            os.remove(filepath)

        return {}


def render(resolution='high'):
    if resolution == 'preview':
        if bpy.context.scene.render.resolution_x >1000:
            # For speed, set the resolution to a common multiple of the tile size
            bpy.context.scene.render.resolution_x = 640
            bpy.context.scene.render.resolution_y = 384

        bpy.context.scene.cycles.samples = 8
        bpy.context.scene.cycles.max_bounces = 6

    elif resolution == 'high':
        # Higher samples and bounces diminishes speed for higher quality images
        bpy.context.scene.cycles.samples = 15
        bpy.context.scene.cycles.max_bounces = 12

    else: # masks
        bpy.context.scene.cycles.samples = 1
        bpy.context.scene.cycles.max_bounces = 1

    bpy.ops.render.render('INVOKE_DEFAULT')


def point_at(obj, target, roll=0):
    """
    Rotate obj to look at target

    :arg obj: the object to be rotated. Usually the camera
    :arg target: the location (3-tuple or Vector) to be looked at
    :arg roll: The angle of rotation about the axis from obj to target in radians. 

    Based on: https://blender.stackexchange.com/a/5220/12947 (ideasman42)      
    Based on: https://blender.stackexchange.com/questions/5210/pointing-the-camera-in-a-particular-direction-programmatically (sadern-alwis)
    """
    if not isinstance(target, mathutils.Vector):
        target = mathutils.Vector(target)
    loc = obj.location
    # direction points from the object to the target
    direction = target - loc
    
    #tracker, rotator = (('-Z', 'Y'),'Z') if obj.type=='CAMERA' else (('X', 'Z'),'Y') #because new cameras points down(-Z), usually meshes point (-Y)
    tracker, rotator = (('-Z', 'Y'),'Z')
    quat = direction.to_track_quat(*tracker)
    
    # /usr/share/blender/scripts/addons/add_advanced_objects_menu/arrange_on_curve.py
    quat = quat.to_matrix().to_4x4()
    rollMatrix = mathutils.Matrix.Rotation(roll, 4, rotator)

    # remember the current location, since assigning to obj.matrix_world changes it
    loc = loc.to_tuple()
    #obj.matrix_world = quat * rollMatrix
    # in blender 2.8 and above @ is used to multiply matrices
    # using * still works but results in unexpected behaviour!
    obj.matrix_world = quat @ rollMatrix
    obj.location = loc