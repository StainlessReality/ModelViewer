bl_info = {
    "name": "Transfer to Headset",
    "author": "Your Name",
    "version": (1, 6),
    "blender": (2, 80, 0),
    "location": "View3D > Side Panel > Headset",
    "description": "Transfers selected objects to the headset application",
    "category": "Object",
}

import bpy
import socket
import os
import struct
import threading
import time

class TransferToHeadsetOperator(bpy.types.Operator):
    """Transfer selected objects to headset"""
    bl_idname = "object.transfer_to_headset"
    bl_label = "Transfer to Headset"

    def execute(self, context):
        code = context.scene.headset_connection_code.strip().upper()
        if len(code) != 4:
            self.report({'ERROR'}, "Connection code must be 4 characters.")
            return {'CANCELLED'}

        port = 5000
        discovery_port = 5001

        # Discover the headset IP address using the code
        headset_ip = self.discover_headset(discovery_port, code)
        if not headset_ip:
            self.report({'ERROR'}, "Could not discover headset on the network.")
            return {'CANCELLED'}

        # Get selected objects
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        # Determine the export file name based on the active object
        active_object = context.view_layer.objects.active
        if active_object is None or active_object not in selected_objects:
            self.report({'ERROR'}, "Active object is not among the selected objects.")
            return {'CANCELLED'}

        export_name = active_object.name

        # Clean the export name to ensure it's a valid filename
        safe_name = bpy.path.clean_name(export_name)
        file_name = f"{safe_name}.glb"

        # Duplicate selected objects with modifiers applied
        duplicates = []
        depsgraph = context.evaluated_depsgraph_get()
        for obj in selected_objects:
            # Evaluate the object with modifiers applied
            obj_eval = obj.evaluated_get(depsgraph)
            mesh = obj_eval.to_mesh()
            if mesh is None:
                print(f"Warning: Could not create mesh for {obj.name}")
                continue
            # Create a new mesh object
            new_mesh = bpy.data.meshes.new_from_object(obj_eval)
            new_obj = bpy.data.objects.new(obj.name + "_export", new_mesh)
            new_obj.matrix_world = obj.matrix_world.copy()
            # Link to the scene collection
            context.collection.objects.link(new_obj)
            duplicates.append(new_obj)
            # Free the temporary mesh
            obj_eval.to_mesh_clear()

        if not duplicates:
            self.report({'ERROR'}, "No duplicates created for export.")
            return {'CANCELLED'}

        # Export duplicates to a temporary GLB file
        temp_dir = bpy.app.tempdir
        temp_file_path = os.path.join(temp_dir, file_name)

        # Select duplicates for export
        bpy.ops.object.select_all(action='DESELECT')
        for obj in duplicates:
            obj.select_set(True)
        context.view_layer.objects.active = duplicates[0]

        # Ensure the export format is GLB
        bpy.ops.export_scene.gltf(
            filepath=temp_file_path,
            use_selection=True,
            export_format='GLB'
        )

        # Delete the duplicates
        for obj in duplicates:
            bpy.data.objects.remove(obj, do_unlink=True)

        # Reselect original objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active_object

        # Read the file data
        try:
            with open(temp_file_path, 'rb') as f:
                file_data = f.read()
        except Exception as e:
            print(f"Error reading temporary file: {e}")
            self.report({'ERROR'}, f"Error reading temporary file: {e}")
            return {'CANCELLED'}

        # Remove the temporary file
        os.remove(temp_file_path)

        # Start the network thread to send the data
        threading.Thread(target=self.send_data, args=(file_data, file_name, headset_ip, port)).start()
        self.report({'INFO'}, f"Model transfer started to {headset_ip}...")
        return {'FINISHED'}

    def discover_headset(self, discovery_port, code):
        # Send a UDP broadcast to discover the headset using the code
        timeout = 5  # seconds
        listen_port = 5002  # Port to listen for responses

        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.bind(("", listen_port))  # Bind to all interfaces on the listening port

        # Enable broadcast mode
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Send the broadcast message containing the code
        try:
            sock.sendto(code.encode('utf-8'), ('<broadcast>', discovery_port))
            print(f"Broadcasting discovery message with code '{code}' on port {discovery_port}...")
        except Exception as e:
            print(f"Failed to send broadcast message: {e}")
            sock.close()
            return None

        # Listen for responses
        start_time = time.time()
        while True:
            try:
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    print("Discovery timeout reached.")
                    break
                data, addr = sock.recvfrom(1024)
                response = data.decode('utf-8')
                if response == "Headset-Discovery-Response":
                    print(f"Discovered headset at {addr[0]}")
                    sock.close()
                    return addr[0]
            except socket.timeout:
                print("Socket timed out waiting for response.")
                break
            except Exception as e:
                print(f"Error during discovery: {e}")
                break

        sock.close()
        return None

    def send_data(self, file_data, file_name, headset_ip, port):
        # Prepare data for sending
        name_bytes = file_name.encode('utf-8')
        name_length = len(name_bytes)
        file_length = len(file_data)

        # Create the data packet
        packet = struct.pack('>I', name_length) + name_bytes + struct.pack('>Q', file_length) + file_data

        # Send the file over TCP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # Set a timeout of 30 seconds
            print(f"Connecting to {headset_ip}:{port}")
            sock.connect((headset_ip, port))
            print("Connection established. Sending data...")
            sock.sendall(packet)
            print("Data sent. Waiting for acknowledgment...")
            # Wait for acknowledgment
            response = sock.recv(1024)
            sock.close()
            if response.decode('utf-8') == 'Success':
                print("Model transferred successfully.")
            else:
                print("Failed to transfer model.")
        except socket.timeout:
            print("Connection timed out.")
        except Exception as e:
            print(f"Failed to transfer model: {e}")

class TransferToHeadsetPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport Sidebar"""
    bl_label = "Transfer to Headset"
    bl_idname = "VIEW3D_PT_transfer_to_headset"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # 'UI' for the Sidebar (N-panel)
    bl_category = "Headset"  # This will be the tab name in the Sidebar

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Code input field with larger scale
        row = layout.row()
        row.scale_y = 2.0  # Increase vertical scale
        row.scale_x = 2.0  # Increase horizontal scale
        row.prop(scene, "headset_connection_code", text="Connection Code")

        layout.separator()

        # Add a button to start the transfer
        row = layout.row()
        row.operator("object.transfer_to_headset", icon='EXPORT')

class TransferToHeadsetPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    port: bpy.props.IntProperty(
        name="Port",
        description="Port number used by the headset application",
        default=5000,
    )

    discovery_port: bpy.props.IntProperty(
        name="Discovery Port",
        description="UDP port used for headset discovery",
        default=5001,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "port")
        layout.prop(self, "discovery_port")

def menu_func(self, context):
    self.layout.operator(TransferToHeadsetOperator.bl_idname)

def register():
    bpy.utils.register_class(TransferToHeadsetPreferences)
    bpy.utils.register_class(TransferToHeadsetOperator)
    bpy.utils.register_class(TransferToHeadsetPanel)
    bpy.types.VIEW3D_MT_object.append(menu_func)
    bpy.types.Scene.headset_connection_code = bpy.props.StringProperty(
        name="Connection Code",
        description="Enter the 4-character code displayed on the headset",
        maxlen=4,
        default=""
    )

def unregister():
    bpy.utils.unregister_class(TransferToHeadsetPreferences)
    bpy.utils.unregister_class(TransferToHeadsetOperator)
    bpy.utils.unregister_class(TransferToHeadsetPanel)
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    del bpy.types.Scene.headset_connection_code

if __name__ == "__main__":
    register()
