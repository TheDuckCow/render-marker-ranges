# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


bl_info = {
	"name": "Render Marker Ranges",
	"category": "Render",
	"version": (1, 0),
	"blender": (2, 80, 0),
	"location": "3D View > View > Render marker ranges",
	"description": "Tool to render segments of the timeline",
	"warning": "",
	"wiki_url": "https://github.com/TheDuckCow/render-marker-ranges",
	"author": "Patrick W. Crawford <support@theduckcow.com>",
	"tracker_url":"https://github.com/TheDuckCow/render-marker-ranges/issues"
}

import os

import importlib
if "bpy" in locals():
	importlib.reload(bpy)
else:
	import bpy


# -----------------------------------------------------------------------------
# Utility functions and structure classes


# Set of render style options
RENDER_TYPES = [
	('viewport_render', 'Viewport render', ''),
	('viewport_solid', 'Viewport solid', ''),
	('full_render', 'Full render', '')]


def make_annotations(cls):
	"""Add annotation attribute to class fields to avoid Blender 2.8 warnings"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
	if bl_props:
		if '__annotations__' not in cls.__dict__:
			setattr(cls, '__annotations__', {})
		annotations = cls.__dict__['__annotations__']
		for k, v in bl_props.items():
			annotations[k] = v
			delattr(cls, k)
	return cls


class MarkerRange(object):
	"""Class for containing structure of a marker range"""
	def __init__(self, name, start_frame, end_frame):
		self.name = name
		self.start_frame = start_frame
		self.end_frame = end_frame
		self.id = str(start_frame)+"-"+str(name)

	def __repr__(self):
		return "Marker range id:{} start:{} end:{}".format(
			self.id, self.start_frame, self.end_frame)

	def __str__(self):
		return "{} ({} - {})".format(
			self.name, self.start_frame, self.end_frame)


def get_marker_ranges(context, end_marker_key=None):
	"""Returns an ordered list of ranges for all detected ranges in the scene

	Returns:
		List of: (Name, start frame, end frame)
	"""

	if not end_marker_key:
		end_marker_key = ''

	marker_dict = {marker.frame: marker.name for marker in context.scene.timeline_markers}
	markers_sorted = sorted(list(marker_dict))
	marker_sets = []
	prior_blank = False
	for marker_frame in markers_sorted:
		# update the prior marker (if any) with this marker's end frame, as
		# the prior range should always end with ANY marker
		if marker_sets and not prior_blank:
			marker_sets[-1].end_frame = marker_frame - 1 # avoid double renders

		# However, never start a new range if it's named after the end_marker key
		if marker_dict[marker_frame] == end_marker_key:
			prior_blank = True
			continue
		else:
			prior_blank = False

		# initialize with placeholder endframe
		marker_sets.append(
			MarkerRange(marker_dict[marker_frame], marker_frame, marker_frame))

	# update the last marker if needed
	if not marker_sets:
		return []
	if marker_sets[-1].end_frame == marker_sets[-1].start_frame:
		marker_sets[-1].end_frame = context.scene.frame_end

	return marker_sets


def get_marker_ranges_enum(self, context):
	"""Return the enum formatted list of render ranges available"""
	return [(
			itm.id,
			"{} ({} - {})".format(
				itm.name, itm.start_frame, itm.end_frame),
			"Render range {}: {} to {}".format(
				itm.name, itm.start_frame, itm.end_frame))
		for itm in get_marker_ranges(context, None)]


def render_marker_range(context, render_style, marker_id=None):
	"""Render all or a single marker set with a given set of render settings"""

	if not hasattr(context.scene, "display") or not hasattr(context.scene.display, "shading"):
		return "No display or shading in space data"

	# capture initial settings
	init_output_location = context.scene.render.filepath
	init_frame_start = context.scene.frame_start
	init_frame_end = context.scene.frame_end
	init_shading_space = context.space_data.shading.type
	init_overlay = context.space_data.overlay.show_overlays
	init_shading_type = context.scene.display.shading.type

	# force camera view
	# bpy.ops.view3d.view_camera()
	for area in context.screen.areas:
		if area.type == 'VIEW_3D':
			area.spaces[0].region_3d.view_perspective = 'CAMERA'

	# Render all or one
	if marker_id:
		# render the single provided marker range
		matching_ranges = [marker for marker in get_marker_ranges(context)
			if marker.id == marker_id]
		if not matching_ranges:
			return "Could not find specified marker range " + str(marker_id)
		marker_range = matching_ranges[0]
		render_single_marker_range(context, render_style, marker_range)
	else:
		# render all marker ranges
		for marker_range in get_marker_ranges(context):
			render_single_marker_range(context, render_style, marker_range)

	# be sure to re-apply old settings
	context.scene.render.filepath = init_output_location
	context.scene.frame_start = init_frame_start
	context.scene.frame_end = init_frame_end

	#context.space_data.viewport_shade = init_viewport_shading
	context.scene.display.shading.type = init_shading_type
	context.space_data.shading.type = init_shading_space
	context.space_data.overlay.show_overlays = init_overlay

	return None


def render_single_marker_range(context, render_style, marker_range):
	"""Render a single marker set with a given set of render settings"""

	init_output = context.scene.render.filepath
	base = os.path.basename(context.scene.render.filepath)
	if base.endswith('_') or base.endswith('-'):
		base = base[:-1]
	dir_output = os.path.dirname(context.scene.render.filepath)

	# setup new paths and settings
	marker_path = marker_range.id # slugify to be OS filename safe
	new_output = os.path.join(
		dir_output,
		marker_path,
		"{}_{}_".format(base, marker_path))
	context.scene.render.filepath = new_output
	context.scene.frame_start = marker_range.start_frame
	context.scene.frame_end = marker_range.end_frame

	# set new settings
	if render_style == "viewport_render":
		context.scene.display.shading.type = 'RENDERED'
		context.space_data.shading.type =  'RENDERED'
		context.space_data.overlay.show_overlays = False

		context.view_layer.update()
		bpy.ops.render.opengl(animation=True)
		# TODO: change to 'INVOKE_DEFAULT' with prior bpy.app.handlers.render_complete

	elif render_style == "viewport_solid":
		context.scene.display.shading.type = 'SOLID'
		context.space_data.shading.type =  'SOLID'
		context.space_data.overlay.show_overlays = False

		context.view_layer.update()
		bpy.ops.render.opengl(animation=True)

	elif render_style == "full_render":
		context.view_layer.update()
		bpy.ops.render.render(animation=True) # use_viewport=True?

	else:
		raise Exception("Not a value render_type")

	context.scene.render.filepath = init_output


# def update_current_marker_range(scene, context):
# 	"""Frame handler for updating what is registered as the active frame marker"""


# -----------------------------------------------------------------------------
# Blender classes


class RMR_OT_render_single_marker_range(bpy.types.Operator):
	"""Render animations for a single marker range"""
	bl_idname = "scene.render_single_marker_range"
	bl_label = "Render marker range"
	bl_options = {'REGISTER'} #, 'UNDO'}

	marker_id = bpy.props.EnumProperty(
		name="Marker range",
		items=get_marker_ranges_enum,
		description="Select the marker range to render")

	render_style = bpy.props.EnumProperty(
		items = RENDER_TYPES,
		name = "Render type"
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		res = render_marker_range(context, self.render_style, self.marker_id)
		if res:
			self.report({"ERROR"}, res)
			return {'CANCELLED'}
		return {'FINISHED'}


class RMR_OT_render_all_marker_ranges(bpy.types.Operator):
	"""Render animations for a single marker range"""
	bl_idname = "scene.render_all_marker_ranges"
	bl_label = "Render all marker ranges"
	bl_options = {'REGISTER'} #, 'UNDO'}

	render_style = bpy.props.EnumProperty(
		items = RENDER_TYPES,
		name = "Render type"
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		rendered = 0
		for marker_range in get_marker_ranges(context):
			res = render_marker_range(context, self.render_style, marker_range.id)
			if res:
				self.report({"ERROR"},
					"Err during {}: {}".format(marker_range.id, res))
				return {'CANCELLED'}
			print("Rendered range "+marker_range.id)
			rendered += 1

		self.report({"INFO"}, "Rendered {} ranges".format(rendered))
		return {'FINISHED'}


class RMR_MT_marker_ranges(bpy.types.Menu):
	"""Panel for managing marker ranges"""
	bl_label = "Render marker ranges"
	bl_idname = "RMR_MT_marker_ranges"

	def draw(self, context):
		col = self.layout.column()
		all_ranges = get_marker_ranges(context)
		if not all_ranges:
			col.label(text="(no markers found)")
			return

		# col.prop(context.scene, "render_marker_range_style", text=None, expand=True)
		ops = col.operator("scene.render_all_marker_ranges")
		# ops.render_style = context.scene.render_marker_range_style

		col.separator()
		for marker_range in all_ranges:
			ops = col.operator(
				"scene.render_single_marker_range",
				text=str(marker_range))
			ops.marker_id = marker_range.id
			# ops.render_style = context.scene.render_marker_range_style


def VIEW3D_MT_view_append(self, context):
	"""Append to the view dropdown menu"""
	self.layout.menu(RMR_MT_marker_ranges.bl_idname, icon='RENDER_ANIMATION')


# -----------------------------------------------------------------------------
# Registration


classes = (
	RMR_OT_render_single_marker_range,
	RMR_OT_render_all_marker_ranges,
	RMR_MT_marker_ranges
	)


def register():
	bpy.types.Scene.render_marker_range_style = bpy.props.EnumProperty(
		name = "Render styles",
		description = "Style of rendering to apply",
		items = RENDER_TYPES)

	for cls in classes:
		make_annotations(cls)
		bpy.utils.register_class(cls)

	bpy.types.VIEW3D_MT_view.append(VIEW3D_MT_view_append)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	if VIEW3D_MT_view_append in bpy.types.VIEW3D_MT_view:
		bpy.types.VIEW3D_MT_view.remove(VIEW3D_MT_view_append)

	del bpy.types.Scene.render_marker_range_style


if __name__ == "__main__":
	register()
