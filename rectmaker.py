from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from sourcepp import vtfpp
import random, copy, math, os, re
from pathlib import Path


supported_formats = (".png",".jpg",".jpeg",".bmp",".tif","tiff",".webp",".psd",".vtf")

class RectangleTool:
    def __init__(self, master):
        self.master = TkinterDnD.Tk() if master is None else master
        self.master.title("RectMaker")

        self.canvas = tk.Canvas(master, bg="gray", cursor="arrow")
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind("<<Drop>>", self.on_drop)
        
        self.canvas.drop_target_register(DND_FILES)
        self.sidebar = tk.Frame(master,width = 150)
        self.sidebar.pack(side="right",fill="y")
        
        self.listbar = tk.Frame(master,width = 200)
        self.listbar.pack(side="left",fill="y")
        
        self.rect_list = tk.Listbox(self.listbar)
        self.rect_list.pack(fill=tk.BOTH,expand=True)

        self.undo_stack = []
        self.redo_stack = []

        self.current_rect_file = None

        self.draw_grid = False
        self.grid_size = 16

        self.rect_list.bind("<<ListboxSelect>>",self.on_rect_list_select)
        

        self.coord_vars = {
            "x": tk.StringVar(),
            "y": tk.StringVar(),
            "w": tk.StringVar(),
            "h": tk.StringVar()
        }

        for i, key in enumerate(["x","y","w","h"]):
            tk.Label(self.sidebar,text=key.upper()).grid(row=i,column=0,sticky="w")
            entry = tk.Entry(self.sidebar,textvariable=self.coord_vars[key],width=10)
            entry.grid(row=i, column=1, pady=2, padx=5)
            entry.bind("<Return>",self.update_selected_from_fields)
        self.canvas.pack(fill="both", expand=True)

        self.scale_window = None
        self.rectangles = []
        self.current_rect = None
        self.start_x = 0
        self.start_y = 0
        self.copied_rect = None

        self.unsaved_changes = False
        self.redraw_background = False

        self.output_scale = 1.0

        self.image = None
        self.tk_image = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None

        self.selected_rect = None
        self.drag_offset = (0,0)

        self.resize_mode = None
        self.handle_size = 6

        self.cached_background = None
        self.cached_scale = None

        self.background_image = None
        self.transparent_rectangles = []
        
        self.create_menu()
        self.bind_events()

    def random_color(self):
        r = random.randint(0,255)
        g = random.randint(0,255)
        b = random.randint(0,255)
        return (r,g,b)

    def rgb_to_hex(self,r, g, b):
        return '#{:02X}{:02X}{:02X}'.format(r, g, b)
 
    def create_menu(self):
        menu = tk.Menu(self.master)
        self.master.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="File", menu=file_menu)
        #file_menu.add_command(label="Import Image", command=self.load_image)
        #file_menu.add_command(label="Open .rect", command=self.import_rectangles)
        #file_menu.add_command(label="Open .vmt",command=self.open_vmt)
        file_menu.add_command(label="Open",command= self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save,accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...",command=self.export_rectangles)
        
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.quit)

        edit_menu = tk.Menu(menu,tearoff=0)
        edit_menu.add_command(label="Undo",command=self.undo, accelerator = "Ctrl+Z")
        edit_menu.add_command(label="Redo",command=self.redo,accelerator="Ctrl+Y")
        menu.add_cascade(label="Edit",menu=edit_menu)

        tools_menu = tk.Menu(menu,tearoff=0)
        tools_menu.add_command(label="Move/Translate",command=self.open_scale_window,accelerator = "Ctrl+M")
        tools_menu.add_command(label="Special Save",command=self.open_custom_save_window)
        menu.add_cascade(label="Tools",menu=tools_menu)

    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_left_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_left_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self.on_middle_mouse_down)
        self.canvas.bind("<B2-Motion>", self.on_middle_mouse_drag)
        self.canvas.bind("<ButtonRelease-2>",self.on_middle_mouse_release)

        self.canvas.bind("<Configure>",self.on_window_resize)
        self.master.bind("<Delete>",self.delete_selected_rectangle)
        self.master.bind("<Control-z>", lambda e: self.undo())
        self.master.bind("<Control-y>", lambda e: self.redo())
        self.master.bind("<Control-c>",self.copy_rectangle)
        self.master.bind("<Control-v>",self.paste_rectangle)
        self.master.bind("<Control-s>",self.save)

        self.master.bind("<Up>",self.on_up_arrow)
        self.master.bind("<Down>",self.on_down_arrow)
        self.master.bind("<Left>",self.on_left_arrow)
        self.master.bind('<Right>',self.on_right_arrow)

        self.master.bind("g",self.toggle_grid)
        self.master.bind("=",self.increase_grid)
        self.master.bind("-",self.decrease_grid)

        self.master.bind("<plus>",self.increase_grid)
        self.master.bind("<KP_Subtract>",self.decrease_grid)
        self.master.bind("<Key>", self.debug_key)
        self.master.bind("<Control-m>",lambda e: self.open_scale_window())
    
    def open_image_error_window(self):
        messagebox.showinfo("Message","You tried to open a .rect file without an image loaded. Open an image first!")
        
    def open_custom_save_window(self):
        window = tk.Toplevel(self.master)
        window.title = "Custom Save"
        window.wm_attributes("-topmost",True)
        savelabel = tk.Label(window,text="Save As:")
        savelabel.grid(row=0,column=0,sticky="w")
        file_path = tk.StringVar()
        tk.Entry(window,textvariable=file_path,width=40).grid(row=0,column=1)
        def browse_file():
            path = filedialog.asksaveasfilename(defaultextension=".rect", filetypes=[("Rect Files", "*.rect")])
            if path:
                file_path.set(path)
    
        tk.Button(window,text="Browse...",command=browse_file).grid(row=0,column=3,sticky="w")

        tk.Label(window,text="Output Scale:").grid(row=1,column=0,sticky="w")
        output_scale = tk.StringVar(value="1.0")
        tk.Entry(window,textvariable=output_scale).grid(row=1,column=1,sticky="w")

        def on_custom_save():
            try:
                path = file_path.get()
                scale = float(output_scale.get())
                self.output_scale = scale
                if path:
                    self.export_rectangles_to_path(path)
                    self.current_rect_file = path
                    self.update_window_title()
                    window.destroy()
            except ValueError:
                tk.messagebox.showerror("Invalid Scale","Please enter a valid float value.")
        
        tk.Button(window,text="Save",command=on_custom_save).grid(row=2,column=1,pady=10)

    def open_scale_window(self):
        if self.scale_window is not None:
            return
        
        xscale = tk.StringVar(value="1.0")
        yscale = tk.StringVar(value="1.0")
        xtranslate = tk.StringVar(value="0")
        ytranslate = tk.StringVar(value="0")

        window = tk.Toplevel(self.master)
        window.title = "Move/Scale"
        window.attributes("-topmost",True)
        tk.Label(window,text="X Scale:").grid(row=0,column=0,sticky="w")
        tk.Entry(window,textvariable=xscale).grid(row=0,column=1)
        tk.Label(window,text="Y Scale:").grid(row=1,column=0,sticky="w")
        tk.Entry(window,textvariable=yscale).grid(row=1,column=1)
        tk.Label(window,text="X Move:").grid(row=0,column=2,sticky="w")
        tk.Entry(window,textvariable=xtranslate).grid(row=0,column=3)
        tk.Label(window,text="Y Move:").grid(row=1,column=2,sticky="w")
        tk.Entry(window,textvariable=ytranslate).grid(row=1,column=3)

        checkvar = tk.IntVar()

        tk.Checkbutton(window,text="Apply to all",variable=checkvar,onvalue=1,offvalue=0).grid(row=2,column=1)

        def apply():
            self.handle_translation(float(xscale.get()),float(yscale.get()),int(xtranslate.get()),int(ytranslate.get()),checkvar.get())

        tk.Button(window,text="Apply",command=apply).grid(row=2,column=2)
        self.scale_window = window

        window.protocol("WM_DELETE_WINDOW", self.on_close_scale_window())

    def on_close_scale_window(self):
        self.scale_window = None
    def apply_translations(self,rect,xscale,yscale,xmove,ymove,all):
            x0,y0,x1,y1,fill,image,scaled_image,scale = self.rectangles[rect]
            if all:
                x0 *= xscale
                x1 *= xscale
                y0 *= yscale
                y1 *= yscale
            else:
                width = x1 - x0
                height = y1 - y0
                y1 = y0 + height * yscale
                x1 = x0 + width * xscale

            x0 += xmove
            x1 += xmove
            y0 += ymove
            y1 += ymove

            self.rectangles[rect] = (int(x0),int(y0),int(x1),int(y1),fill,image,scaled_image,scale)


    def handle_translation(self,xscale,yscale,xmove,ymove,all):
        if all:
            for idx, r in enumerate(self.rectangles):
                self.apply_translations(idx,xscale,yscale,xmove,ymove,all)
        else:
            if self.selected_rect is not None:
                self.apply_translations(self.selected_rect,xscale,yscale,xmove,ymove,all)
        
        self.save_undo_state()
        self.redraw()
        self.update_rectangle_list()
        self.update_window_title()

    def debug_key(self,event):
        print(f"Key pressed: keysym={event.keysym}, keycode={event.keycode}, char={event.char}")


    def on_window_resize(self,event):
        print("Window Resize Dected\n")
        self.redraw()

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Images, Rects, VMT's", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp;*.qoi;*.psd;*.vtf;*.vmt;*.rect")])
        if not path:
            return
        if path.endswith(".rect"):
            self.import_rectangles_from_path(path)
        elif path.endswith(".vmt"):
            self.parse_vmt(path)
        else:
            self.load_image_from_path(path)

    def load_image_from_path(self,path):
        print(f"load path {path}")
        self.image = None
        if path.endswith(".vtf"):
            vtf = vtfpp.VTF(path)
            if vtf:
                self.image = Image.frombuffer('RGB', (vtf.width_for_mip(0), vtf.height_for_mip(0)), vtf.get_image_data_as(vtfpp.ImageFormat.RGB888))
        else:
            self.image = Image.open(path)
        self.rectangles.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_rectangle_list()
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.redraw_background = True
        self.redraw()

    def export_rectangles(self):
        if not self.rectangles:
            return
        
        file = filedialog.asksaveasfilename(defaultextension=".rect", filetypes=[("Rect Files", "*.rect")])
        if file:
            self.export_rectangles_to_path(file)

    def export_rectangles_to_path(self,file):
        if not self.rectangles:
            return

        with open(file, "w") as f:
            write_custom_data = self.output_scale != 1.0
            if write_custom_data:
                f.write(f"output_scale {self.output_scale}\n")
            f.write("Rectangles\n{\n")
            for r in self.rectangles:
                x0, y0, x1, y1,*_ = r
                if write_custom_data:
                    x0 = int(x0 * self.output_scale)
                    y0 = int(y0 * self.output_scale)
                    x1 = int(x1 * self.output_scale)
                    y1 = int(y1 * self.output_scale)
                
                f.write("\trectangle\n\t{\n")
                f.write(f"\t\t\"min\" \"{x0} {y0}\"\n")
                f.write(f"\t\t\"max\" \"{x1} {y1}\"\n")
                f.write("\t}\n")
            f.write("}")
            
        self.current_rect_file = file
        self.update_window_title()

    def open_vmt(self):
        file = filedialog.askopenfilename(filetypes=[(".vmt Files", "*.vmt")])
        if not file:
            return
        self.parse_vmt(file)

    def update_window_title(self):
        if self.current_rect_file:
            filename = os.path.basename(self.current_rect_file)
            if self.unsaved_changes == True:
                self.master.title(f"RectMaker - *{filename}")
            else:
                self.master.title(f"RectMaker - {filename}")
        else:
            if not self.image:
                self.master.title("RectMaker")
            else:
                if not self.rectangles:
                    self.master.title("RectMaker - Untitled")
                else:
                    self.master.title("RectMaker - *Untitled")

    def parse_vmt(self,file):
        try:
            print(f"{file}")
            with open(file,"r") as f:
                lines = f.readlines()

                texture_parse = re.compile(r'^\s*"?\$basetexture"?\s+"?([^"\s]+)"?')
                rect_parse = re.compile(r'^\s*"?%rectanglemap"?\s+"?([^"\s]+)"?')

                for line in lines:
                    texture = texture_parse.match(line)
                    rectfile = rect_parse.match(line)
                    if texture:
                        relative = texture.group(1).strip()
                        if Path(relative).suffix == "":
                            relative += ".vtf"
                        
                        tex_path = self.resolve_absolute_path(file,relative)
                        
                        tex_path = Path(tex_path).as_posix()
                        final_path = str(tex_path)
                        print(f"final path {tex_path}")
                        self.load_image_from_path(final_path)
                        

                    if rectfile:
                        relative = rectfile.group(1).strip()
                        relative_path = Path(relative)
                        if relative_path.suffix == "":
                            relative += ".rect"
                        rect_path = self.resolve_absolute_path(file,relative)
                        rect_path = Path(rect_path).as_posix()
                        final_path = str(rect_path)
                        self.import_rectangles_from_path(str(final_path))

        except ValueError as e:
            print(f"Error reading .vmt, Exception: {e}")

    def resolve_absolute_path(self,vmt,path):
        try:
            vmt_dir = Path(vmt).parent
            dir = str(vmt_dir)
            abspath = dir.partition("materials")
            dir = abspath[0] + abspath[1] + "/" + path
            absdir = Path(dir).absolute()
            return str(absdir)
        except Exception as e:
            print("failed to resolve absolute path")

        

    def import_rectangles_from_path(self,file):
        print(f"rectpath: {file}")
        if self.image is None:
            self.open_image_error_window()
            return
        
        try:
            with open(file,"r") as f:
                lines = f.readlines()

            self.rectangles.clear()
            i = 0

            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("output_scale"):
                    parts = line.split()
                    if len(parts) > 1:
                        scale = float(parts[1])
                        print(f"scale {scale}")
                        i += 1
                else:
                    scale = 1.0

                if line == "rectangle":
                    if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                        min_line = lines[i + 2].strip()
                        max_line = lines[i + 3].strip()

                        x0, y0 = map(int, min_line.split('"')[3].split())
                        x1, y1 = map(int, max_line.split('"')[3].split())

                        x0, x1 = sorted((x0, x1))
                        y0, y1 = sorted((y0, y1))

                        x0 = int(x0/scale)
                        x1 = int(x1/scale)
                        y0 = int(y0/scale)
                        y1 = int(y1/scale)

                        fill = self.random_color()
                        width = x1 - x0
                        height = y1 - y0
                        
                        image = self.create_transparent_rectangle((x1-x0),(y1-y0),fill)
                        zoomed_image = image.resize((int(width * self.scale),int(height * self.scale)),Image.NEAREST)
                        scaled_image = ImageTk.PhotoImage(zoomed_image)
                        self.rectangles.append((x0, y0, x1, y1,fill,image,scaled_image,self.scale))
                        self.update_rectangle_list()

                        i += 5
                    else:
                        i += 1
                else:
                    i += 1
            self.selected_rect = None
            self.redraw_background = True
            self.current_rect_file = file
            self.output_scale = 1.0
            self.redraw()
            print(f"Imported {len(self.rectangles)} rectangles from file.")
        except Exception as e:
            print(f"Error importing rectangles: {e}")

    def on_drop(self,event):
        path = event.data.strip('{}')
        print(f"Dropped: {path}")
        if path.lower().endswith(supported_formats):
            self.load_image_from_path(path)
        elif path.lower().endswith(".rect"):
            self.import_rectangles_from_path(path)
        elif path.lower().endswith(".vmt"):
            self.parse_vmt(path)

    def save(self,event=None):
        if not self.rectangles:
            return
        if self.current_rect_file:
            self.export_rectangles_to_path(self.current_rect_file)
        else:
            self.export_rectangles()
        self.unsaved_changes = False
        self.update_window_title()

    def to_image_coords(self, screen_x, screen_y):
        ix = int((screen_x - self.offset_x) / self.scale)
        iy = int((screen_y - self.offset_y) / self.scale)
        return ix, iy

    def to_screen_coords(self, image_x, image_y):
        sx = int(image_x * self.scale + self.offset_x)
        sy = int(image_y * self.scale + self.offset_y)
        return sx, sy

    def on_mouse_wheel(self, event):

        if not event.state & 0x0004:
            return
        
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        mouse_x, mouse_y = event.x, event.y
        img_x, img_y = self.to_image_coords(mouse_x, mouse_y)

        self.scale *= zoom_factor
        self.offset_x = mouse_x - img_x * self.scale
        self.offset_y = mouse_y - img_y * self.scale
        self.redraw()

    def on_middle_mouse_down(self, event):
        self.pan_start = (event.x, event.y)
        self.canvas.config(cursor="sizing")

    def on_middle_mouse_drag(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (event.x, event.y)
            self.redraw()
            
    def on_middle_mouse_release(self,event):
        self.canvas.config(cursor="arrow")


    def within_selection_bounds(self,x,y,rect):
        x0,y0,x1,y1 = rect
        
        w = x1 - x0
        h = y1 - y0

        margin_x = (w / 2) * 0.25
        margin_y = (h / 2) * 0.25

        inner_x0 = x0 + margin_x
        inner_x1 = x1 - margin_x
        inner_y0 = y0 + margin_y
        inner_y1 = y1 - margin_y

        print(f"Margin: {margin_x} {margin_y}")
        print(f"Safe Coords: {inner_x0} {inner_y0} x {inner_x1} {inner_y1}")
        print(f"mouse pos {x} {y}")

        return inner_x0 <= x <= inner_x1 and inner_y0 <= y <= inner_y1
    
    def on_left_mouse_down(self, event):
        x, y = self.to_image_coords(event.x, event.y)
        print(f"Clickpos {event.x} {event.y}")

        if self.image is None:
            return
        
        if event.state & 0x0001:
            self.start_x = x
            self.start_y = y
            self.current_rect = None
            self.selected_rect = None
            self.canvas.config(cursor="cross")
            return

        if self.selected_rect is not None:
            x0,y0,x1,y1,*_ = self.rectangles[self.selected_rect]
            corners = {
                'nw': (x0,y0),
                'ne':(x1,y0),
                'sw':(x0,y1),
                'se':(x1,y1),
                }
            for mode,(cx,cy) in corners.items():
                sx,sy = self.to_screen_coords(cx,cy)
                if abs(event.x - sx) <= self.handle_size and abs(event.y - sy) <= self.handle_size:
                    print("clicking corner")
                    self.resize_mode = mode
                    self.save_undo_state()
                    return
                
        self.resize_mode = None
        self.selected_rect = None
                
        for idx, (x0,y0,x1,y1,fill,image,scale_image,zoom) in enumerate(self.rectangles):
            print(f"{x0} {y0} x {x1} {y1}")
            if self.within_selection_bounds(x,y,(x0,y0,x1,y1)):
                self.selected_rect = idx
                self.drag_offset = (x - x0, y - y0)
                self.save_undo_state()
                break
            

        
        self.redraw()
        self.update_fields_from_selected()

        
    def grid_snap_value(self,value):
        return math.ceil(self.grid_size * round(value/self.grid_size))
    
    def on_left_mouse_drag(self, event):
        if self.image is None:
            return
        
        if self.selected_rect is None:
            if event.state & 1:
                x, y = self.to_image_coords(event.x, event.y)

                if self.draw_grid is True:
                    x = self.grid_snap_value(x)
                    y = self.grid_snap_value(y)
                    self.start_x = self.grid_snap_value(self.start_x)
                    self.start_y = self.grid_snap_value(self.start_y)
                    
                sx0, sy0 = self.to_screen_coords(self.start_x, self.start_y)
                sx1, sy1 = self.to_screen_coords(x, y)
            else:
                return

            if self.current_rect:
                self.canvas.delete(self.current_rect)

            self.current_rect = self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="lime", dash=(2, 2))
        else:
            x,y = self.to_image_coords(event.x,event.y)
            x = max(0,min(x,self.image.width - 1))
            y = max(0,min(y,self.image.height - 1))


            rect = self.rectangles[self.selected_rect]
            x0, y0, x1, y1, fill,*_= rect
            width = max(1,int((x1 - x0)*self.scale))
            height = max(1,int((y1-y0)*self.scale))
            image = self.create_transparent_rectangle((x1-x0),(y1-y0),fill)
            zoomed_image = image.resize((width,height),Image.NEAREST)
            scaled_image = ImageTk.PhotoImage(zoomed_image)

            if self.resize_mode:
                if self.resize_mode == 'nw':
                    x0, y0 = x, y
                elif self.resize_mode == 'ne':
                    x1, y0 = x,y
                elif self.resize_mode == 'sw':
                    x0, y1 = x,y
                elif self.resize_mode == 'se':
                    x1,y1 = x,y
                
                x0,x1 = sorted((x0,x1))
                y0,y1 = sorted((y0,y1))

                if self.draw_grid is True:
                    x0 = self.grid_snap_value(x0)
                    y0 = self.grid_snap_value(y0)
                    x1 = self.grid_snap_value(x1)
                    y1 = self.grid_snap_value(y1)
            else:
                imagewidth = self.image.width
                imageheight = self.image.height
                dx, dy = self.drag_offset
                x0 = x - dx
                y0 = y - dy
                
                if x0 <= 0:
                    x0 = 0
                if y0 <= 0:
                    y0 = 0
                
                if self.draw_grid is True:
                    x0 = self.grid_snap_value(x0)
                    y0 = self.grid_snap_value(y0)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]

                x1 = x0 + width
                if x1 >= imagewidth:
                    x1 = imagewidth
                    x0 = x1 - width
                
                y1 = y0 + height
                if y1 >= imageheight:
                    y1 = imageheight
                    y0 = y1 - height

            self.rectangles[self.selected_rect] = (x0,y0,x1,y1,fill,image,scaled_image,self.scale)
            self.update_rectangle_list()
            self.redraw()
            self.update_fields_from_selected()
            

    def on_left_mouse_up(self, event):
        if self.current_rect is None:
            return
        if self.image is None:
            return
        
        self.selected_rect = None
        self.resize_mode = None

        if self.current_rect:
                self.canvas.delete(self.current_rect)

        if not event.state & 0x0001:
            return
        
        self.save_undo_state()
        x0, y0 = self.start_x, self.start_y
        x1, y1 = self.to_image_coords(event.x, event.y)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))

        self.canvas.config(cursor="arrow")
        fill = self.random_color()

        if self.image:
            width, height = self.image.size
            x0 = max(0, min(x0, width - 1))
            x1 = max(0, min(x1, width))
            y0 = max(0, min(y0, height - 1))
            y1 = max(0, min(y1, height))

        if self.draw_grid is True:
            x0 = self.grid_snap_value(x0)
            y0 = self.grid_snap_value(y0)
            x1 = self.grid_snap_value(x1)
            y1 = self.grid_snap_value(y1)
        
        w = x1 - x0
        h = y1 - y0
        image = self.create_transparent_rectangle(w,h,fill)
        zoomed_image = image.resize((int(w * self.scale),int(h * self.scale)),Image.NEAREST)
        scaled_image = ImageTk.PhotoImage(zoomed_image)
        self.rectangles.append((x0, y0, x1, y1,fill,image,scaled_image,self.scale))
        self.update_rectangle_list()
        self.current_rect = None
        self.redraw()
        self.update_fields_from_selected()
        self.update_window_title()

    def clear_canvas(self):
        all_items = self.canvas.find_all()
        background = self.canvas.find_withtag("background")
        rectangles = self.canvas.find_withtag("rectangles")
        delete_items = set(all_items) - set(background) - set(rectangles)
        for item in delete_items:
            self.canvas.delete(item)
        
    # --- Redrawing Everything ---
    def redraw(self):
        self.clear_canvas()
        if not self.image:
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Visible area in image space
        visible_left, visible_top = self.to_image_coords(0, 0)
        visible_right, visible_bottom = self.to_image_coords(canvas_width, canvas_height)


        # Draw scaled image
        if self.cached_background is None or self.scale != self.cached_scale or self.redraw_background is True:
            display_img = self.image.resize(
                (int(self.image.width * self.scale), int(self.image.height * self.scale)),
                resample=Image.NEAREST
            )
            self.cached_background = display_img
            self.cached_scale = self.scale
            self.redraw_background = False

        src_x0 = max(0,int(-self.offset_x))
        src_y0 = max(0,int(-self.offset_y))
        src_x1 = min(self.cached_background.width,src_x0 + canvas_width)
        src_y1 = min(self.cached_background.height,src_y0 + canvas_height)

        draw_x = max(0, self.offset_x)
        draw_y = max(0, self.offset_y)

        if src_x1 > src_x0 and src_y1 > src_y0: #Crop background image so we aren't drawing outside of our canvas
            cropped = self.cached_background.crop((src_x0,src_y0,src_x1,src_y1))
            self.tk_image = ImageTk.PhotoImage(cropped)
        else:
            self.tk_image = ImageTk.PhotoImage(self.cached_background)


        if self.background_image is None:
            self.background_image = self.canvas.create_image(draw_x, draw_y, anchor="nw", image=self.tk_image,tags = "background")
        else:
            self.canvas.coords(self.background_image,draw_x,draw_y)
            self.canvas.itemconfig(self.background_image,image=self.tk_image)
        
            
        self.canvas_images = []

        while len(self.transparent_rectangles) > len(self.rectangles):
            bogus_id = self.transparent_rectangles.pop()
            if bogus_id is not None:
                self.canvas.delete(bogus_id)

        while len(self.transparent_rectangles) < len(self.rectangles):
            self.transparent_rectangles.append(None)

        for idx, r in enumerate(self.rectangles):
            
            x0,y0,x1,y1, fill, image,scaled_image,zoom_scale = r

            if x1 < visible_left or x0 > visible_right or y1 < visible_top or y0 > visible_bottom:#ignore rectangles that are outside of our canvas bounds
                if self.transparent_rectangles[idx] is not None:
                    self.canvas.delete(self.transparent_rectangles[idx])
                    self.transparent_rectangles[idx] = None
                continue

            w = int(x1 - x0)
            h = int(y1 - y0)
            zw = max(1,int(w * self.scale))
            zh = max(1,int(h * self.scale))
            zw2 = int(image.width * self.scale)
            zh2 = int(image.height * self.scale)

            if zw < 1 or zh < 1:
                if self.transparent_rectangles[idx] is not None:
                    self.canvas.delete(self.transparent_rectangles[idx])
                    self.transparent_rectangles[idx] = None
                continue

            if self.scale != zoom_scale or zw2 != zw or zh2 != zh:
                print("Scale changed, resizing rectangle image\n")
                print(f"w = {zw} h = {zh} w2 = {zw2} h2 = {zh2}")
                zi = image.resize((zw,zh),Image.NEAREST)
                scaled_image = ImageTk.PhotoImage(zi)
                self.rectangles[idx] = (x0,y0,x1,y1,fill,image,scaled_image,self.scale)

            
            sx0, sy0 = self.to_screen_coords(x0, y0)
            sx1, sy1 = self.to_screen_coords(x1, y1)
            
            #self.canvas_images.append(scaled_image)

            textx = int(sx0 + (zw * 0.5))
            texty = int(sy0 + (zh * 0.5))

            
            outline = "yellow" if idx == self.selected_rect else "red"
            width = 3 if idx == self.selected_rect else 1
            textfill = "white" if idx == self.selected_rect else "black"

            if self.transparent_rectangles[idx] is None:
                self.transparent_rectangles[idx] = self.canvas.create_image(sx0,sy0,anchor="nw",image = scaled_image,tags = "rectangles")
                print("trans rect not found, creating\n")
            else:
                self.canvas.coords(self.transparent_rectangles[idx],sx0,sy0)
                self.canvas.itemconfig(self.transparent_rectangles[idx],image=scaled_image)
                print("trans rect found, moving\n")
                
            self.canvas.create_rectangle(sx0,sy0,sx1,sy1,outline=outline,width=1)
            self.canvas.create_text(textx,texty,text=f"#{idx}",fill=textfill)           

            if idx == self.selected_rect:
                corners = [(sx0,sy0),(sx1,sy0),(sx0,sy1),(sx1,sy1)]
                for hx,hy in corners:
                    hid = self.canvas.create_rectangle(
                            hx - self.handle_size, hy - self.handle_size,
                            hx + self.handle_size, hy + self.handle_size,
                            outline = "cyan", width = 1
                            )
                    

        if self.draw_grid:
            xcount = int(self.image.width / self.grid_size)
            ycount = int(self.image.height / self.grid_size)

            for i in range(xcount+1):
                x,y = self.to_screen_coords(i * self.grid_size,0)
                x1,y1 = self.to_screen_coords(i * self.grid_size,self.image.height)
                self.canvas.create_line(x,y,x1,y1,fill="gray",width=1,dash=(2, 2))
            for i in range(ycount+1):
                x,y = self.to_screen_coords(0,i * self.grid_size)
                x1,y1 = self.to_screen_coords(self.image.width,i * self.grid_size)
                self.canvas.create_line(x,y,x1,y1,fill="gray",width=1,dash=(2, 2))

    def delete_selected_rectangle(self,event=None):
        if self.selected_rect is not None:
            del self.rectangles[self.selected_rect]
            
            self.selected_rect = None
            self.clear_canvas()
            self.redraw()
            self.update_rectangle_list()

    def update_fields_from_selected(self):
        
        if self.selected_rect is None:
            for key in self.coord_vars:
                self.coord_vars[key].set("")
            return


        x0,y0,x1,y1,*_ = self.rectangles[self.selected_rect]
        x = int(x0)
        y = int(y0)
        w = max(1,int(x1 - x0))
        h = max(1,int(y1 - y0))

        self.coord_vars["x"].set(str(x))
        self.coord_vars["y"].set(str(y))
        self.coord_vars["w"].set(str(w))
        self.coord_vars["h"].set(str(h))

        self.update_rectangle_list()

    def update_selected_from_fields(self, event = None):
        if self.selected_rect is None:
            return

        try:
            x = max(1,int(self.coord_vars["x"].get()))
            y = max(1,int(self.coord_vars["y"].get()))
            w = max(1,int(self.coord_vars["w"].get()))
            h = max(1,int(self.coord_vars["h"].get()))
            x1 = x+w
            y1 = y+h

            _,_,_,_,fill,image,scaled_image,scale = self.rectangles[self.selected_rect]
            self.rectangles[self.selected_rect] = (x,y,x1,y1,fill,image,scaled_image,scale)
            self.redraw()

            self.update_rectangle_list()

        except ValueError:
            pass
    def create_transparent_rectangle(self,width,height,fill):
        alpha = 120
        r,g,b = fill
        rgba = (r,g,b,alpha)
        image = Image.new("RGBA",(width,height),rgba)
        return image

    def update_rectangle_list(self):
        self.rect_list.delete(0,tk.END)

        for idx, (x0,y0,x1,y1,fill,*_) in enumerate(self.rectangles):
            w = abs(x1 - x0)
            h = abs(y1 - y0)
            self.rect_list.insert(tk.END,f"#{idx} ({x0},{y0}) {w}x{h}")
            r,g,b = fill
            color = self.rgb_to_hex(r,g,b)
            self.rect_list.itemconfig(tk.END,foreground=color)
        if self.selected_rect is not None:
            self.rect_list.select_set(self.selected_rect)

    def on_rect_list_select(self,event):
        if not self.rect_list.curselection():
            return
        index = self.rect_list.curselection()[0]
        self.selected_rect = index
        self.redraw()
        self.update_fields_from_selected()


    def save_undo_state(self):
        self.undo_stack.append(copy.copy(self.rectangles))
        self.redo_stack.clear()
        self.unsaved_changes = True
        self.update_window_title()

    def undo(self):
        if not self.undo_stack:
            return
        self.selected_rect = None
        self.redo_stack.append(copy.copy(self.rectangles))
        self.rectangles = self.undo_stack.pop()
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()
    def redo(self):
        if not self.redo_stack:
            return
        self.selected_rect = None
        self.undo_stack.append(copy.copy(self.rectangles))
        self.rectangles = self.redo_stack.pop()
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()

    def on_up_arrow(self,event):
        if self.selected_rect == None:
            return
        self.master.focus()
        self.save_undo_state()
        rect = self.rectangles[self.selected_rect]

        x0,y0,x1,y1,fill,image,scaled_image,scale = rect

        increment = self.grid_size if self.draw_grid == True else 1

        if event.state & 1:
            y0 -= increment
        elif event.state & 4:
            y1 -=increment
        else:
            y0 -=increment
            y1 -=increment

        self.rectangles[self.selected_rect] = (x0,y0,x1,y1,fill,image,scaled_image,scale)
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()
    def on_down_arrow(self,event):
        if self.selected_rect == None:
            return
        self.master.focus()
        rect = self.rectangles[self.selected_rect]

        x0,y0,x1,y1,fill,image,scaled_image,scale = rect

        increment = self.grid_size if self.draw_grid == True else 1

        if event.state & 1:
            y0 += increment
        elif event.state & 4:
            y1 +=increment
        else:
            y0 +=increment
            y1 +=increment

        self.rectangles[self.selected_rect] = (x0,y0,x1,y1,fill,image,scaled_image,scale)
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()
    def on_left_arrow(self,event):
        if self.selected_rect == None:
            return
        self.master.focus()
        self.save_undo_state()
        rect = self.rectangles[self.selected_rect]

        x0,y0,x1,y1,fill,image,scaled_image,scale = rect

        increment = self.grid_size if self.draw_grid == True else 1

        if event.state & 1:
            x1 -= increment
        elif event.state & 4:
            x0 -=increment
        else:
            x0 -=increment
            x1 -=increment

        self.rectangles[self.selected_rect] = (x0,y0,x1,y1,fill,image,scaled_image,scale)
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()
        
    def on_right_arrow(self,event):
        if self.selected_rect == None:
            return
        
        self.master.focus()
        self.save_undo_state()
        
        rect = self.rectangles[self.selected_rect]

        x0,y0,x1,y1,fill,image,scaled_image,scale = rect

        increment = self.grid_size if self.draw_grid == True else 1

        if event.state & 1:
            x1 += increment
        elif event.state & 4:
            x0 +=increment
        else:
            x0 +=increment
            x1 +=increment

        self.rectangles[self.selected_rect] = (x0,y0,x1,y1,fill,image,scaled_image,scale)
        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()

    def copy_rectangle(self,event):
        if self.selected_rect == None:
            return

        self.copied_rect = self.rectangles[self.selected_rect]
        
    def paste_rectangle(self,event):
        if self.copied_rect == None:
            return
        
        self.save_undo_state()

        mouse_x,mouse_y = self.to_image_coords(event.x - 120,event.y)

        x0,y0,x1,y1,*_ = self.copied_rect
        wide = x1 - x0
        tall = y1 - y0

        offx0 = round(mouse_x - wide / 2)
        offy0 = round(mouse_y - tall / 2)
        offx1 = offx0 + wide
        offy1 = offy0 + tall

        fill = self.random_color()
        
        image = self.create_transparent_rectangle(wide,tall,fill)
        zoomed_image = image.resize((int(wide * self.scale),int(tall * self.scale)),Image.NEAREST)
        scaled_image = ImageTk.PhotoImage(zoomed_image)

        self.rectangles.append((offx0, offy0, offx1, offy1,fill,image,scaled_image,self.scale))

        self.update_rectangle_list()
        self.update_fields_from_selected()
        self.redraw()
        
    def increase_grid(self,event):
        self.grid_size *= 2
        self.redraw()
        
    def decrease_grid(self,event):
        if self.grid_size <= 2:
            self.grid_size = 2
            return
        
        self.grid_size /= 2
        self.redraw()
        
    def toggle_grid(self,event):
        self.draw_grid = not self.draw_grid
        self.redraw()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = RectangleTool(root)
    root.mainloop()
